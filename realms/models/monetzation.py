from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from realms.models.orm import Base


class ApiKey(Base):
    """API keys for paid subscribers.

    Keys are stored as SHA-256 hashes. The raw key is shown once at creation.
    """

    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key_prefix: Mapped[str] = mapped_column(String(8), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    label: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    tier: Mapped[str] = mapped_column(String(20), nullable=False, default="pro")
    daily_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=10000)
    monthly_limit: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    stripe_customer_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    stripe_subscription_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    owner_email: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    extra_data: Mapped[Optional[dict]] = mapped_column("extra_data", JSONB, nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class UsageRecord(Base):
    """Per-request usage log for billing and rate limiting."""

    __tablename__ = "usage_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    api_key_id: Mapped[int] = mapped_column(
        ForeignKey("api_keys.id", ondelete="CASCADE"), nullable=False, index=True
    )
    endpoint: Mapped[str] = mapped_column(String(100), nullable=False)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class StripeCustomer(Base):
    """Maps Stripe customers to their subscription state."""

    __tablename__ = "stripe_customers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    stripe_customer_id: Mapped[str] = mapped_column(
        String(100), nullable=False, unique=True, index=True
    )
    stripe_subscription_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    tier: Mapped[str] = mapped_column(String(20), nullable=False, default="pro")
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="incomplete", index=True
    )
    api_key_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("api_keys.id", ondelete="SET NULL"), nullable=True
    )
    api_key_raw: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    extra_data: Mapped[Optional[dict]] = mapped_column("extra_data", JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
