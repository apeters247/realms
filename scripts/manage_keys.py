"""Admin CLI for API key management.

Usage:
  python -m scripts.manage_keys create --email user@example.com --tier pro
  python -m scripts.manage_keys list
  python -m scripts.manage_keys revoke --prefix ro_abc123
  python -m scripts.manage_keys usage --prefix ro_abc123
"""
from __future__ import annotations

import argparse
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from realms.models.monetzation import ApiKey, UsageRecord
from realms.utils.database import get_db_session

TIERS = {
    "free": {"daily_limit": 50, "monthly_limit": None},
    "pro": {"daily_limit": 10000, "monthly_limit": None},
    "enterprise": {"daily_limit": 100000, "monthly_limit": None},
}


def cmd_create(args: argparse.Namespace) -> None:
    tier = args.tier or "pro"
    tier_cfg = TIERS.get(tier, TIERS["pro"])
    raw = f"ro_{secrets.token_hex(24)}"
    prefix = raw[:8]
    key_hash = hashlib.sha256(raw.encode()).hexdigest()

    with get_db_session() as db:
        key = ApiKey(
            key_prefix=prefix,
            key_hash=key_hash,
            label=args.label or f"CLI {tier} — {args.email or 'unknown'}",
            tier=tier,
            daily_limit=tier_cfg["daily_limit"],
            monthly_limit=tier_cfg["monthly_limit"],
            owner_email=args.email,
            is_active=True,
            expires_at=datetime.now(timezone.utc) + timedelta(days=365),
        )
        db.add(key)
        db.commit()
        print(f"Created {tier} API key:")
        print(f"  Key:     {raw}")
        print(f"  Prefix:  {prefix}")
        print(f"  Email:   {args.email or 'none'}")
        print(f"  Tier:    {tier}")
        print(f"  Limit:   {tier_cfg['daily_limit']} req/day")


def cmd_list(args: argparse.Namespace) -> None:
    from realms.models.monetzation import ApiKey
    with get_db_session() as db:
        keys = db.query(ApiKey).order_by(ApiKey.created_at.desc()).all()
        if not keys:
            print("No API keys found.")
            return
        print(f"{'Prefix':<12} {'Tier':<12} {'Active':<8} {'Email':<30} {'Daily':<8} {'Created':<20}")
        print("-" * 90)
        for k in keys:
            print(
                f"{k.key_prefix:<12} {k.tier:<12} {str(k.is_active):<8} "
                f"{(k.owner_email or ''):<30} {k.daily_limit:<8} "
                f"{k.created_at.strftime('%Y-%m-%d') if k.created_at else '':<20}"
            )


def cmd_revoke(args: argparse.Namespace) -> None:
    with get_db_session() as db:
        key = db.query(ApiKey).filter(ApiKey.key_prefix == args.prefix).first()
        if key is None:
            print(f"No key found with prefix {args.prefix}")
            return
        key.is_active = False
        db.commit()
        print(f"Revoked key {key.key_prefix} ({key.owner_email or 'no email'})")


def cmd_usage(args: argparse.Namespace) -> None:
    with get_db_session() as db:
        key = db.query(ApiKey).filter(ApiKey.key_prefix == args.prefix).first()
        if key is None:
            print(f"No key found with prefix {args.prefix}")
            return
        from sqlalchemy import cast, Date
        today = datetime.now(timezone.utc).date()
        total = db.query(UsageRecord).filter(UsageRecord.api_key_id == key.id).count()
        today_count = db.query(UsageRecord).filter(
            UsageRecord.api_key_id == key.id,
            cast(UsageRecord.timestamp, Date) == today,
        ).count()
        print(f"Key:       {key.key_prefix} ({key.owner_email or 'no email'})")
        print(f"Tier:      {key.tier}")
        print(f"Active:    {key.is_active}")
        print(f"Today:     {today_count} / {key.daily_limit}")
        print(f"Total:     {total}")
        print(f"Created:   {key.created_at.strftime('%Y-%m-%d') if key.created_at else 'N/A'}")
        print(f"Expires:   {key.expires_at.strftime('%Y-%m-%d') if key.expires_at else 'Never'}")


def main():
    parser = argparse.ArgumentParser(description="REALMS API key management")
    sub = parser.add_subparsers()

    p_create = sub.add_parser("create", help="Create a new API key")
    p_create.add_argument("--email", help="Owner email")
    p_create.add_argument("--tier", choices=list(TIERS.keys()), default="pro")
    p_create.add_argument("--label", help="Human-readable label")
    p_create.set_defaults(func=cmd_create)

    p_list = sub.add_parser("list", help="List all API keys")
    p_list.set_defaults(func=cmd_list)

    p_revoke = sub.add_parser("revoke", help="Revoke an API key")
    p_revoke.add_argument("--prefix", required=True, help="Key prefix (first 8 chars)")
    p_revoke.set_defaults(func=cmd_revoke)

    p_usage = sub.add_parser("usage", help="Show usage for a key")
    p_usage.add_argument("--prefix", required=True, help="Key prefix (first 8 chars)")
    p_usage.set_defaults(func=cmd_usage)

    args = parser.parse_args()
    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
