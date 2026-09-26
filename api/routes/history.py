"""
api/routes/history.py — Detection history endpoints.

GET    /api/history      — retrieve paginated history
GET    /api/stats         — aggregate statistics
DELETE /api/history      — clear all history
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from api.database import clear_all_history, get_history, get_stats, get_total_count
from api.schemas import HistoryResponse, MessageResponse, StatsResponse

router = APIRouter(prefix="/api", tags=["history"])


@router.get(
    "/history",
    response_model=HistoryResponse,
    summary="Get detection history",
    description="Retrieve paginated detection history, newest first.",
)
async def list_history(
    limit: int = Query(default=50, ge=1, le=500, description="Max entries to return"),
    offset: int = Query(default=0, ge=0, description="Number of entries to skip"),
) -> HistoryResponse:
    """Return paginated detection history."""
    entries = get_history(limit=limit, offset=offset)
    total = get_total_count()
    return HistoryResponse(total=total, entries=entries)


@router.get(
    "/stats",
    response_model=StatsResponse,
    summary="Get detection statistics",
    description="Aggregate statistics from all detection history.",
)
async def detection_stats() -> StatsResponse:
    """Return aggregate detection statistics."""
    stats = get_stats()
    return StatsResponse(stats=stats)


@router.delete(
    "/history",
    response_model=MessageResponse,
    summary="Clear detection history",
    description="Delete all detection history records.",
)
async def delete_history() -> MessageResponse:
    """Clear all detection history."""
    deleted = clear_all_history()
    return MessageResponse(message=f"Cleared {deleted} history record(s).")
