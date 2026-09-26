"""
api/schemas.py — Pydantic request/response models for the VaniGuard API.

All API contracts are defined here as a single source of truth.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ── Detection ──────────────────────────────────────────────────────────────


class DetectionResult(BaseModel):
    """Response payload for POST /api/detect."""

    filename: str = Field(..., description="Original uploaded file name")
    verdict: str = Field(
        ..., description="Human-readable verdict: 'AI-Generated', 'Human', or 'UNCERTAIN'"
    )
    probability: float = Field(
        ..., ge=0.0, le=1.0, description="P(AI-generated) in [0, 1]"
    )
    confidence_pct: float = Field(
        ..., ge=0.0, le=100.0, description="Confidence percentage (0–100)"
    )
    risk_band: str = Field(
        ..., description="Risk band label (e.g. 'HIGH RISK — very likely AI-generated')"
    )
    risk_level: str = Field(
        ..., description="Short risk level: 'high', 'suspicious', 'uncertain', or 'low'"
    )
    duration_s: float = Field(
        ..., description="Actual audio clip duration in seconds"
    )
    is_ai: bool = Field(
        ..., description="True if verdict contains 'AI-Generated'"
    )
    model_loaded: bool = Field(
        ..., description="Whether the ONNX model was actually used (False = random fallback)"
    )


# ── History ────────────────────────────────────────────────────────────────


class HistoryEntry(BaseModel):
    """A single detection history record."""

    id: int = Field(..., description="Auto-incrementing record ID")
    timestamp: str = Field(..., description="ISO-formatted detection timestamp")
    filename: str
    verdict: str
    confidence_pct: float
    risk_band: str
    probability: float


class HistoryResponse(BaseModel):
    """Response payload for GET /api/history."""

    total: int = Field(..., description="Total number of history records")
    entries: list[HistoryEntry] = Field(
        default_factory=list, description="List of history entries (newest first)"
    )


class HistoryStats(BaseModel):
    """Aggregate statistics from detection history."""

    total: int = 0
    ai_detected: int = 0
    human_detected: int = 0
    uncertain: int = 0
    ai_detection_rate: float = 0.0
    avg_confidence: float = 0.0


class StatsResponse(BaseModel):
    """Response payload for GET /api/stats."""

    stats: HistoryStats


class MessageResponse(BaseModel):
    """Generic message response."""

    message: str


# ── Health ─────────────────────────────────────────────────────────────────


class HealthResponse(BaseModel):
    """Response payload for GET /api/health."""

    status: str = Field(..., description="'healthy' or 'degraded'")
    model_loaded: bool = Field(
        ..., description="Whether the ONNX model is loaded and ready"
    )
    model_error: Optional[str] = Field(
        None, description="Error message if model failed to load"
    )
    version: str = Field(default="1.0.0", description="API version")
    uptime_s: float = Field(..., description="Server uptime in seconds")
