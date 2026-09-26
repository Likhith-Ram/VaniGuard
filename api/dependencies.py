"""
api/dependencies.py — Shared dependencies for the FastAPI app.

Holds the ONNX session singleton so it's loaded once at startup and
shared across all request handlers.
"""

from __future__ import annotations

import time
from typing import Any, Optional

from src.model import load_model

# ── Startup timestamp ─────────────────────────────────────────────────────
_start_time: float = time.time()


def get_uptime() -> float:
    """Return server uptime in seconds."""
    return time.time() - _start_time


# ── ONNX session singleton ────────────────────────────────────────────────
_session: Optional[Any] = None
_model_error: Optional[str] = None
_model_loaded: bool = False


def init_model() -> None:
    """Load the ONNX model. Call once at startup."""
    global _session, _model_error, _model_loaded
    _session, _model_error = load_model()
    _model_loaded = _session is not None


def get_session() -> Optional[Any]:
    """Return the ONNX InferenceSession (or None if unavailable)."""
    return _session


def get_model_error() -> Optional[str]:
    """Return the model loading error message (or None if loaded OK)."""
    return _model_error


def is_model_loaded() -> bool:
    """Return True if the ONNX model is loaded and ready."""
    return _model_loaded
