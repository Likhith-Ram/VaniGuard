"""
api/security.py — API-key authentication dependency for VaniGuard.

All protected endpoints declare:

    Depends(require_api_key)

The key is read once at import time from the VANIGUARD_API_KEY environment
variable.  If the variable is absent the server starts but every protected
request is rejected with HTTP 403, making misconfiguration immediately
visible rather than silently insecure.

Constant-time comparison (hmac.compare_digest) prevents timing-oracle
attacks that could allow brute-force key discovery.
"""

from __future__ import annotations

import hmac
import os
from typing import Optional

from fastapi import Header, HTTPException, Security, status
from fastapi.security import APIKeyHeader

# ── Read key at import time — never log this value ────────────────────────
_API_KEY: Optional[str] = os.getenv("VANIGUARD_API_KEY")

# FastAPI security scheme — clients send the key as an HTTP header:
#   X-API-Key: <value>
_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def require_api_key(api_key: Optional[str] = Security(_api_key_header)) -> None:
    """
    FastAPI dependency that enforces API-key authentication.

    Raises HTTP 401 when no key is provided.
    Raises HTTP 403 when the key is present but wrong.
    Uses constant-time comparison to resist timing attacks.

    Usage::

        @app.post("/analyze")
        async def analyze(..., _: None = Depends(require_api_key)):
            ...
    """
    if not _API_KEY:
        # Server is misconfigured — reject all requests rather than being
        # an open relay.  Operator must set VANIGUARD_API_KEY.
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="API key authentication is not configured on this server.",
        )

    if api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-API-Key header.",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    # hmac.compare_digest is constant-time — immune to timing side-channels.
    if not hmac.compare_digest(api_key, _API_KEY):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key.",
        )
