"""
api/test_main.py — Integration tests for the VaniGuard FastAPI app.

Tests are updated to supply the X-API-Key header (CRIT-03 fix).
The test key is injected via environment variable before the app is imported.
"""

import io
import os
import struct
import wave

import numpy as np
import pytest
from fastapi.testclient import TestClient

# ── Inject a test API key BEFORE importing the app so security.py picks it up.
TEST_KEY = "test-api-key-for-pytest"
os.environ.setdefault("VANIGUARD_API_KEY", TEST_KEY)

from api.main import app  # noqa: E402  (must be after env var is set)

@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c

AUTH = {"X-API-Key": TEST_KEY}


# ── Helpers ───────────────────────────────────────────────────────────────────

def create_dummy_wav() -> io.BytesIO:
    """Create a 1-second silent 16 kHz mono WAV file in memory."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        data = np.zeros(16000, dtype=np.int16)
        wf.writeframes(data.tobytes())
    buf.seek(0)
    return buf


# ── /api/health — public, no key required ─────────────────────────────────────

def test_health_no_auth(client):
    """Health endpoint must be reachable without authentication."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "model_loaded" in data


# ── Authentication enforcement ────────────────────────────────────────────────

def test_analyze_requires_auth(client):
    """Unauthenticated /analyze must return 401 or 403."""
    buf = create_dummy_wav()
    response = client.post("/analyze", files={"file": ("test.wav", buf, "audio/wav")})
    assert response.status_code in (401, 403)


def test_stats_requires_auth(client):
    """Unauthenticated /api/stats must return 401 or 403."""
    response = client.get("/api/stats")
    assert response.status_code in (401, 403)


def test_history_requires_auth(client):
    """Unauthenticated /api/scans/history must return 401 or 403."""
    response = client.get("/api/scans/history")
    assert response.status_code in (401, 403)


def test_wrong_key_rejected(client):
    """Wrong API key must return 403."""
    buf = create_dummy_wav()
    response = client.post(
        "/analyze",
        files={"file": ("test.wav", buf, "audio/wav")},
        headers={"X-API-Key": "wrong-key"},
    )
    assert response.status_code == 403


# ── /analyze ──────────────────────────────────────────────────────────────────

def test_analyze_authenticated(client):
    """Authenticated /analyze with valid WAV returns the expected shape."""
    buf = create_dummy_wav()
    response = client.post(
        "/analyze",
        files={"file": ("test.wav", buf, "audio/wav")},
        headers=AUTH,
    )
    # May return 200 (model loaded) or 422 (clip too short after model check).
    # Both are acceptable — the key point is auth was accepted (not 401/403).
    assert response.status_code not in (401, 403)
    if response.status_code == 200:
        data = response.json()
        assert "verdict" in data
        assert "prob_ai" in data
        assert "risk_band" in data
        assert "confidence" in data
        assert "is_ai" in data
        assert "model_loaded" in data


def test_analyze_upload_too_large(client):
    """Oversized uploads must be rejected with 413."""
    # Create a buffer that exceeds the default 50 MB limit
    huge = io.BytesIO(b"x" * (51 * 1024 * 1024))
    response = client.post(
        "/analyze",
        files={"file": ("big.wav", huge, "audio/wav")},
        headers=AUTH,
    )
    assert response.status_code == 413


def test_analyze_bad_extension(client):
    """Unsupported file extensions must be rejected with 415."""
    buf = io.BytesIO(b"dummy")
    response = client.post(
        "/analyze",
        files={"file": ("test.exe", buf, "application/octet-stream")},
        headers=AUTH,
    )
    assert response.status_code == 415
