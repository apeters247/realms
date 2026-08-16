"""Stripe subscription management for REALMS monetization.

Endpoints:
  POST /api/subscriptions/create-checkout  — Create Stripe Checkout session
  POST /api/subscriptions/webhook           — Stripe event webhook
  GET  /api/subscriptions/status            — Check subscription status by API key
"""
from __future__ import annotations

import hashlib
import logging
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from realms.utils.database import get_db_session

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/subscriptions", tags=["subscriptions"])
key_router = APIRouter(tags=["keys"])

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
STRIPE_PRICE_PRO_MONTHLY = os.getenv("STRIPE_PRICE_PRO_MONTHLY", "price_pro_monthly")
PUBLIC_ORIGIN = os.getenv("REALMS_PUBLIC_ORIGIN", "https://realmsoutthere.com")


class CheckoutRequest(BaseModel):
    tier: str = "pro"
    success_path: str = "/app/subscribe/success"


class CheckoutResponse(BaseModel):
    url: str
    session_id: str


class StatusResponse(BaseModel):
    active: bool
    tier: str = ""
    daily_usage: int = 0
    daily_limit: int = 0


class GenerateKeyResponse(BaseModel):
    key: str
    prefix: str
    tier: str = "free"
    daily_limit: int = 50


def _generate_api_key() -> tuple[str, str, str]:
    """Generate a random API key. Returns (raw_key, prefix, hash)."""
    raw = f"ro_{secrets.token_hex(24)}"
    prefix = raw[:8]
    h = hashlib.sha256(raw.encode()).hexdigest()
    return raw, prefix, h


@router.post("/create-checkout")
async def create_checkout(req: CheckoutRequest) -> CheckoutResponse:
    if not STRIPE_SECRET_KEY:
        raise HTTPException(status_code=501, detail="Stripe not configured")

    import stripe
    stripe.api_key = STRIPE_SECRET_KEY

    price_id = STRIPE_PRICE_PRO_MONTHLY

    session = stripe.checkout.Session.create(
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=f"{PUBLIC_ORIGIN}{req.success_path}?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{PUBLIC_ORIGIN}/pricing",
        metadata={"tier": req.tier},
    )
    return CheckoutResponse(url=session.url, session_id=session.id)


@router.post("/webhook")
async def stripe_webhook(request: Request):
    if not STRIPE_SECRET_KEY or not STRIPE_WEBHOOK_SECRET:
        raise HTTPException(status_code=501, detail="Stripe not configured")

    import stripe
    stripe.api_key = STRIPE_SECRET_KEY

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    except (ValueError, stripe.error.SignatureVerificationError) as exc:
        log.warning("Stripe webhook signature verification failed: %s", exc)
        raise HTTPException(status_code=400, detail="invalid signature")

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        await _handle_checkout_completed(session)
    elif event["type"] == "invoice.paid":
        invoice = event["data"]["object"]
        await _handle_invoice_paid(invoice)
    elif event["type"] == "customer.subscription.deleted":
        sub = event["data"]["object"]
        await _handle_subscription_deleted(sub)
    elif event["type"] == "customer.subscription.updated":
        sub = event["data"]["object"]
        await _handle_subscription_updated(sub)

    return {"status": "ok"}


async def _handle_checkout_completed(session: dict) -> None:
    from realms.models.monetzation import ApiKey, StripeCustomer

    customer_id = session.get("customer")
    subscription_id = session.get("subscription")
    email = session.get("customer_details", {}).get("email") or session.get("customer_email")
    tier = session.get("metadata", {}).get("tier", "pro")

    raw_key, prefix, key_hash = _generate_api_key()

    with get_db_session() as db:
        existing = db.query(StripeCustomer).filter(
            StripeCustomer.stripe_customer_id == customer_id
        ).first()
        if existing:
            existing.stripe_subscription_id = subscription_id
            existing.status = "active"
            existing.email = email or existing.email
            existing.tier = tier
            if existing.api_key_id:
                api_key = db.query(ApiKey).filter(ApiKey.id == existing.api_key_id).first()
                if api_key:
                    api_key.is_active = True
                    api_key.expires_at = datetime.now(timezone.utc) + timedelta(days=30)
                    api_key.tier = tier
            db.commit()
            log.info("Updated StripeCustomer %s", customer_id)
            return

        api_key = ApiKey(
            key_prefix=prefix,
            key_hash=key_hash,
            label=f"Stripe {tier} — {email or customer_id}",
            tier=tier,
            daily_limit=10000,
            stripe_customer_id=customer_id,
            stripe_subscription_id=subscription_id,
            owner_email=email,
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        )
        db.add(api_key)
        db.flush()

        customer = StripeCustomer(
            stripe_customer_id=customer_id,
            stripe_subscription_id=subscription_id,
            email=email,
            tier=tier,
            status="active",
            api_key_id=api_key.id,
            api_key_raw=raw_key,
        )
        db.add(customer)
        db.commit()

        log.info(
            "Provisioned API key %s for customer %s (%s)",
            prefix, customer_id, email,
        )


async def _handle_invoice_paid(invoice: dict) -> None:
    from realms.models.monetzation import ApiKey

    subscription_id = invoice.get("subscription")
    if not subscription_id:
        return
    with get_db_session() as db:
        key = db.query(ApiKey).filter(
            ApiKey.stripe_subscription_id == subscription_id
        ).first()
        if key:
            key.expires_at = datetime.now(timezone.utc) + timedelta(days=30)
            key.is_active = True
            db.commit()
            log.info("Renewed API key %s via invoice payment", key.key_prefix)


async def _handle_subscription_deleted(sub: dict) -> None:
    from realms.models.monetzation import ApiKey

    subscription_id = sub.get("id")
    with get_db_session() as db:
        key = db.query(ApiKey).filter(
            ApiKey.stripe_subscription_id == subscription_id
        ).first()
        if key:
            key.is_active = False
            db.commit()
            log.info("Deactivated API key %s — subscription cancelled", key.key_prefix)


async def _handle_subscription_updated(sub: dict) -> None:
    from realms.models.monetzation import ApiKey

    subscription_id = sub.get("id")
    status = sub.get("status")
    with get_db_session() as db:
        key = db.query(ApiKey).filter(
            ApiKey.stripe_subscription_id == subscription_id
        ).first()
        if key:
            key.is_active = status == "active"
            if status in ("past_due", "unpaid"):
                key.expires_at = datetime.now(timezone.utc) + timedelta(days=3)
            db.commit()
            log.info("Updated API key %s — subscription status=%s", key.key_prefix, status)


@key_router.post("/api/keys/generate")
async def generate_free_key() -> GenerateKeyResponse:
    """Generate a free-tier API key. No auth required."""
    from realms.models.monetzation import ApiKey

    raw_key, prefix, key_hash = _generate_api_key()
    with get_db_session() as db:
        key = ApiKey(
            key_prefix=prefix,
            key_hash=key_hash,
            tier="free",
            daily_limit=50,
            is_active=True,
            expires_at=datetime.now(timezone.utc) + timedelta(days=365),
        )
        db.add(key)
        db.commit()
    return GenerateKeyResponse(key=raw_key, prefix=prefix)


@router.get("/session/{session_id}/key")
async def get_session_key(session_id: str) -> dict:
    """Retrieve the raw API key for a completed Stripe Checkout session."""
    if not STRIPE_SECRET_KEY:
        raise HTTPException(status_code=501, detail="Stripe not configured")
    import stripe
    stripe.api_key = STRIPE_SECRET_KEY
    try:
        session = stripe.checkout.Session.retrieve(session_id)
    except stripe.error.StripeError:
        raise HTTPException(status_code=404, detail="Session not found")
    customer_id = session.customer
    if not customer_id:
        raise HTTPException(status_code=404, detail="No customer on session")
    with get_db_session() as db:
        from realms.models.monetzation import StripeCustomer
        cust = db.query(StripeCustomer).filter(
            StripeCustomer.stripe_customer_id == customer_id
        ).first()
        if not cust or not cust.api_key_raw:
            raise HTTPException(status_code=404, detail="Key not yet provisioned")
        return {"key": cust.api_key_raw, "tier": cust.tier}


@router.get("/status")
async def subscription_status(request: Request) -> StatusResponse:
    from realms.models.monetzation import ApiKey, UsageRecord

    api_key = request.headers.get("X-API-Key") or request.headers.get("x-api-key")
    if not api_key:
        raise HTTPException(status_code=401, detail="X-API-Key header required")

    key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    with get_db_session() as db:
        key = db.query(ApiKey).filter(
            ApiKey.key_hash == key_hash,
            ApiKey.is_active == True,
        ).first()
        if key is None:
            raise HTTPException(status_code=403, detail="Invalid or deactivated API key")

        today = datetime.now(timezone.utc).date()
        from sqlalchemy import cast, Date
        daily_usage = db.query(UsageRecord).filter(
            UsageRecord.api_key_id == key.id,
            cast(UsageRecord.timestamp, Date) == today,
        ).count()

        return StatusResponse(
            active=key.is_active,
            tier=key.tier,
            daily_usage=daily_usage,
            daily_limit=key.daily_limit,
        )
