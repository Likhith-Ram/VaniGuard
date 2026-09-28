"""
api/main.py - FastAPI entry point for VaniGuard

Single source of truth for all HTTP + WebSocket endpoints.
All routes share one SQLAlchemy async session (PostgreSQL via asyncpg).
"""
import time
from typing import Optional
from uuid import UUID
import numpy as np

from fastapi import FastAPI, UploadFile, File, WebSocket, WebSocketDisconnect, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, case, select

from src.pipeline import (
    preprocess_audio,
    load_model,
    run_inference,
    classify,
    StreamPipeline
)
from src.risk_engine import RiskEngine
from api.core.database import get_db
from api.repositories.scan_repository import ScanRepository
from api.models.models import AudioScan, Verdict
from api.routes import users

# ── App setup ─────────────────────────────────────────────────────────────────
app = FastAPI(
    title="VaniGuard API",
    description="Real-time AI voice cloning detection for Indian languages.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Model singleton ───────────────────────────────────────────────────────────
_START_TIME = time.time()
session, _model_error = load_model()
_model_loaded = session is not None

app.include_router(users.router)


# ── /analyze — audio detection ────────────────────────────────────────────────
@app.post("/analyze", tags=["detection"])
async def analyze(file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    """
    Upload an audio file (WAV/MP3/OGG/FLAC/M4A) for AI voice detection.
    Returns verdict, risk band, probability, and confidence.
    """
    audio_bytes = await file.read()
    ext = file.filename.rsplit(".", 1)[-1].lower() if file.filename else "wav"

    mel_norm, mel_tensor, duration_s = preprocess_audio(audio_bytes, ext)
    prob_ai = run_inference(session, mel_tensor)
    verdict_str, risk_band, risk_css = classify(prob_ai)

    is_ai = "AI-Generated" in verdict_str
    confidence = prob_ai if is_ai else (1.0 - prob_ai)

    if is_ai:
        db_verdict = Verdict.synthetic_clone
    elif "UNCERTAIN" in verdict_str:
        db_verdict = Verdict.suspicious
    else:
        db_verdict = Verdict.genuine

    repo = ScanRepository(db)
    await repo.create_scan(
        impersonation_risk_score=float(prob_ai * 100),
        verdict=db_verdict,
        language="English",
        spectral_features={"confidence": float(confidence), "duration": float(duration_s)},
    )

    return {
        "verdict": verdict_str,
        "risk_band": risk_band,
        "risk_css": risk_css,
        "prob_ai": round(float(prob_ai), 4),
        "confidence": round(float(confidence), 4),
        "confidence_pct": round(float(confidence * 100), 1),
        "duration_s": round(float(duration_s), 2),
        "is_ai": is_ai,
        "model_loaded": _model_loaded,
    }


# ── /api/scans/history — cursor-paginated history ─────────────────────────────
@app.get("/api/scans/history", tags=["history"])
async def get_scans_history(
    limit: int = Query(default=20, ge=1, le=200),
    cursor: Optional[UUID] = None,
    verdict: Optional[Verdict] = None,
    language: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """Cursor-paginated scan history (newest first)."""
    repo = ScanRepository(db)
    scans, next_cursor = await repo.get_history(
        limit=limit, cursor=cursor, verdict=verdict, language=language
    )
    return {
        "items": [
            {
                "id": str(scan.id),
                "language": scan.language,
                "impersonation_risk_score": scan.impersonation_risk_score,
                "verdict": scan.verdict.value if hasattr(scan.verdict, "value") else scan.verdict,
                "scanned_at": scan.scanned_at.isoformat() if scan.scanned_at else None,
            }
            for scan in scans
        ],
        "next_cursor": str(next_cursor) if next_cursor else None,
    }


# ── /api/history — offset-paginated compat alias (mobile) ────────────────────
@app.get("/api/history", tags=["history"])
async def get_history_compat(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """Offset-paginated history — backward-compat alias for mobile."""
    query = (
        select(AudioScan)
        .order_by(AudioScan.scanned_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(query)
    scans = result.scalars().all()

    count_result = await db.execute(select(func.count()).select_from(AudioScan))
    total = count_result.scalar() or 0

    return {
        "total": total,
        "entries": [
            {
                "id": str(scan.id),
                "timestamp": scan.scanned_at.isoformat() if scan.scanned_at else None,
                "filename": f"scan_{str(scan.id)[:8]}",
                "verdict": scan.verdict.value if hasattr(scan.verdict, "value") else scan.verdict,
                "confidence_pct": scan.impersonation_risk_score,
                "risk_band": (
                    "HIGH RISK" if scan.impersonation_risk_score >= 80
                    else "SUSPICIOUS" if scan.impersonation_risk_score >= 60
                    else "UNCERTAIN" if scan.impersonation_risk_score >= 40
                    else "LOW RISK"
                ),
                "probability": round(scan.impersonation_risk_score / 100, 4),
            }
            for scan in scans
        ],
    }


# ── /api/stats — aggregate statistics ────────────────────────────────────────
@app.get("/api/stats", tags=["history"])
async def get_stats(db: AsyncSession = Depends(get_db)):
    """Aggregate statistics across all scans."""
    result = await db.execute(
        select(
            func.count().label("total"),
            func.sum(
                case((AudioScan.verdict == Verdict.synthetic_clone, 1), else_=0)
            ).label("ai_detected"),
            func.sum(
                case((AudioScan.verdict == Verdict.genuine, 1), else_=0)
            ).label("human_detected"),
            func.sum(
                case((AudioScan.verdict == Verdict.suspicious, 1), else_=0)
            ).label("uncertain"),
            func.avg(AudioScan.impersonation_risk_score).label("avg_confidence"),
        ).select_from(AudioScan)
    )
    row = result.one()
    total = row.total or 0
    ai_detected = row.ai_detected or 0
    return {
        "stats": {
            "total": total,
            "ai_detected": ai_detected,
            "human_detected": row.human_detected or 0,
            "uncertain": row.uncertain or 0,
            "ai_detection_rate": round((ai_detected / total * 100) if total else 0.0, 1),
            "avg_confidence": round(float(row.avg_confidence or 0), 1),
        }
    }


# ── /api/health — health check ────────────────────────────────────────────────
@app.get("/api/health", tags=["health"])
async def health_check():
    """Server health, model status, and uptime."""
    return {
        "status": "healthy" if _model_loaded else "degraded",
        "model_loaded": _model_loaded,
        "model_error": _model_error,
        "version": "1.0.0",
        "uptime_s": round(time.time() - _START_TIME, 1),
    }


# ── /stream — WebSocket live monitoring ──────────────────────────────────────
@app.websocket("/stream")
async def stream(websocket: WebSocket):
    """
    WebSocket endpoint for real-time live monitoring.
    Client sends raw PCM float32 chunks at 16 kHz (mono).
    Server responds with JSON per analysis window.
    """
    await websocket.accept()

    sp = StreamPipeline(session=session)
    engine = RiskEngine()
    engine.reset()

    try:
        while True:
            data = await websocket.receive_bytes()
            chunk = np.frombuffer(data, dtype=np.float32)
            results = sp.write(chunk)

            for r in results:
                state = engine.ingest(r.prob_ai)
                await websocket.send_json({
                    "window_index": r.window_index,
                    "prob_ai": float(r.prob_ai),
                    "verdict": r.verdict,
                    "risk_band": r.risk_band,
                    "risk_css": r.risk_css,
                    "status_level": state.level.name,
                    "status_confidence": float(state.confidence),
                })
    except WebSocketDisconnect:
        results = sp.flush()
        for r in results:
            engine.ingest(r.prob_ai)


