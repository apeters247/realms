"""In-memory rate limiter via slowapi. Default 60 req/min per IP.

For a multi-worker deploy this would need a Redis backend; acceptable for
the current single-uvicorn-process setup.
"""
from __future__ import annotations

import os

from slowapi import Limiter
from slowapi.util import get_remote_address


def _burst_per_minute() -> str:
    rpm = os.getenv("REALMS_RATE_LIMIT_PER_MINUTE", "60")
    return f"{rpm}/minute"


limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[_burst_per_minute()],
)
