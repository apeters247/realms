"""FastAPI dependencies shared across routes.

``require_review_token`` gates Phase 4 write endpoints. The bearer token is
read from env var ``REALMS_REVIEW_TOKEN``. If unset, review endpoints return
503 Service Unavailable — an explicit refusal rather than a silent open door.
"""
from __future__ import annotations

import os

from fastapi import Header, HTTPException, status


def require_review_token(authorization: str | None = Header(default=None)) -> str:
    """Verify the caller supplied a matching review token.

    Returns the reviewer name (derived from env ``REALMS_REVIEW_REVIEWER`` or
    ``"anonymous"``) so the handler can stamp audit rows. Raises:

      * 503 if no server-side token is configured (review is disabled)
      * 401 if no Authorization header is supplied
      * 403 if the supplied token does not match
    """
    expected = os.getenv("REALMS_REVIEW_TOKEN")
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="review disabled — set REALMS_REVIEW_TOKEN to enable",
        )
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    prefix = "Bearer "
    token = authorization[len(prefix):] if authorization.startswith(prefix) else authorization
    if token != expected:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="invalid review token",
        )
    return os.getenv("REALMS_REVIEW_REVIEWER", "anonymous")
