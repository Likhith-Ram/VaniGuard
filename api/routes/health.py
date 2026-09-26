"""
api/routes/health.py — Health check endpoint.

GET /api/health — returns model status, version, and uptime.
"""

from __future__ import annotations

from fastapi import APIRouter

from api.dependencies import get_model_error, get_uptime, is_model_loaded
from api.schemas import HealthResponse

router = APIRouter(prefix="/api", tags=["health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    description="Check server health, model status, and uptime.",
)
async def health_check() -> HealthResponse:
    """Return the current health status of the API."""
    model_ok = is_model_loaded()
    return HealthResponse(
        status="healthy" if model_ok else "degraded",
        model_loaded=model_ok,
        model_error=get_model_error(),
        version="1.0.0",
        uptime_s=round(get_uptime(), 1),
    )
