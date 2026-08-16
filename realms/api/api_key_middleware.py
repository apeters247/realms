"""API key authentication middleware for paid access.

Checks X-API-Key header on designated routes, looks up the key hash,
enforces daily/monthly limits, and logs usage.

Public routes (/, /api/health, /docs, /app, /pricing) are excluded.
"""
from __future__ import annotations

import hashlib
import logging
import os
import re
from datetime import datetime, timezone
from typing import Optional

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from realms.utils.database import get_db_session

log = logging.getLogger(__name__)

PUBLIC_PATHS = re.compile(
    r"^(?:"
    r"/api/health"
    r"|/api/subscriptions/"
    r"|/api/keys/generate"
    r"|/docs/?$"
    r"|/redoc/?$"
    r"|/openapi.json"
    r"|/app/"
    r"|/pricing/?$"
    r"|/subscribe/"
    r"|/e/"
    r"|/og/"
    r"|/$"
    r")"
)


def _hash_key(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


class APIKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: ASGIApp) -> Response:
        if PUBLIC_PATHS.match(request.url.path):
            return await call_next(request)

        api_key = request.headers.get("X-API-Key") or request.headers.get("x-api-key")
        if not api_key:
            return JSONResponse(
                status_code=401,
                content={"error": "missing_api_key", "message": "X-API-Key header required. Get a key at https://realmsouthere.com/pricing"},
            )

        key_hash = _hash_key(api_key)
        with get_db_session() as session:
            from realms.models.monetzation import ApiKey, UsageRecord

            key = session.query(ApiKey).filter(
                ApiKey.key_hash == key_hash,
                ApiKey.is_active == True,
            ).first()

            if key is None:
                return JSONResponse(
                    status_code=403,
                    content={"error": "invalid_api_key", "message": "API key not found or deactivated"},
                )

            if key.expires_at and datetime.now(timezone.utc) > key.expires_at:
                return JSONResponse(
                    status_code=403,
                    content={"error": "expired_api_key", "message": "API key expired. Renew at https://realmsouthere.com/pricing"},
                )

            today = datetime.now(timezone.utc).date()
            from sqlalchemy import cast, Date
            daily_usage = session.query(UsageRecord).filter(
                UsageRecord.api_key_id == key.id,
                cast(UsageRecord.timestamp, Date) == today,
            ).count()
            if daily_usage >= key.daily_limit:
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": "daily_limit_exceeded",
                        "message": f"Daily limit of {key.daily_limit} requests reached. Upgrade at https://realmsouthere.com/pricing",
                        "daily_limit": key.daily_limit,
                    },
                )

            if key.monthly_limit:
                month_start = today.replace(day=1)
                monthly_usage = session.query(UsageRecord).filter(
                    UsageRecord.api_key_id == key.id,
                    cast(UsageRecord.timestamp, Date) >= month_start,
                ).count()
                if monthly_usage >= key.monthly_limit:
                    return JSONResponse(
                        status_code=429,
                        content={
                            "error": "monthly_limit_exceeded",
                            "message": f"Monthly limit of {key.monthly_limit} requests reached.",
                            "monthly_limit": key.monthly_limit,
                        },
                    )

            key.last_used_at = datetime.now(timezone.utc)

        response = await call_next(request)

        with get_db_session() as session:
            record = UsageRecord(
                api_key_id=key.id,
                endpoint=request.url.path,
                status_code=response.status_code,
            )
            session.add(record)
            session.commit()

        response.headers["X-Realms-Key-Status"] = "active"
        response.headers["X-Realms-Key-Tier"] = key.tier
        return response
