"""
api/main.py — FastAPI entry point for VaniGuard.

Key architecture decisions
--------------------------
* CPU-bound work (librosa preprocessing + ONNX inference) is dispatched to a
  dedicated ThreadPoolExecutor so the asyncio event loop is NEVER blocked.
  See CRIT-04 and HIGH-08 in the audit report.

* A module-level ThreadPoolExecutor is created once at startup and shut down
  cleanly via the lifespan context manager.  We do NOT create a new executor
  per request (which would spawn uncontrolled threads).

* A Semaphore caps the number of concurrent inference jobs, preventing CPU
  saturation under burst load.

* All non-health endpoints require the X-API-Key header (see api/security.py).
  See CRIT-03, CRIT-06 in the audit report.

* CORS allow_origins is now environment-configurable (not wildcard).
  See CRIT-01 in the audit report.

* File uploads are size-limited (50 MB hard cap) and validated before
  expensive processing.  See CRIT-05, HIGH-01, CRIT-08, HIGH-19.

* WebSocket messages are size-capped (1 MB) to prevent memory exhaustion.
  See HIGH-12 in the audit report.

* Internal error details (filesystem paths, stack traces) are never surfaced
  to clients.  See HIGH-19 in the audit report.
"""

from __future__ import annotations

import asyncio
import functools
import os
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from typing import Optional
from uuid import UUID

import numpy as np

from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
    Query,
    UploadFile,
    File,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, case, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.database import get_db
from api.dependencies import get_session, init_model, is_model_loaded, get_model_error, get_uptime
from api.models.models import AudioScan, Verdict
from api.repositories.scan_repository import ScanRepository
from api.routes import users
from api.security import require_api_key
from src.pipeline import (
    preprocess_audio,
    run_inference,
    classify,
    StreamPipeline,
)
from src.risk_engine import RiskEngine

# ── Configuration from environment ────────────────────────────────────────────
# CORS: restrict to the actual frontend origin in production.
# Set VANIGUARD_FRONTEND_ORIGIN to your deployed Next.js URL.
_FRONTEND_ORIGIN: str = os.getenv(
    "VANIGUARD_FRONTEND_ORIGIN", "http://localhost:3000"
)

# Maximum upload size: 50 MB — hard ceiling before reading any bytes.
_MAX_UPLOAD_BYTES: int = int(os.getenv("VANIGUARD_MAX_UPLOAD_BYTES", str(50 * 1024 * 1024)))

# Maximum WebSocket message size: 1 MB  (~65 000 float32 samples, far more
# than any single 256 ms chunk needs).
_MAX_WS_MSG_BYTES: int = int(os.getenv("VANIGUARD_MAX_WS_MSG_BYTES", str(1 * 1024 * 1024)))

# Maximum concurrent inference jobs across all WebSocket connections.
# Prevents N simultaneous connections from saturating all CPU cores.
_MAX_CONCURRENT_INFERENCE: int = int(os.getenv("VANIGUARD_MAX_CONCURRENT_INFERENCE", "4"))

# ── Executor (module-level, shared across all requests) ───────────────────────
# CPU-bound work (librosa + ONNX) must NOT run on the asyncio event loop.
# A dedicated executor with a bounded worker count is created once and reused.
_executor: ThreadPoolExecutor | None = None

# Semaphore to bound concurrent inference jobs (set in lifespan).
_inference_semaphore: asyncio.Semaphore | None = None


@asynccontextmanager
async def lifespan(application: FastAPI):
    """
    Startup / shutdown lifecycle for the FastAPI application.

    Startup: load ONNX model + create the thread-pool executor.
    Shutdown: cleanly drain and shut down the executor.
    """
    global _executor, _inference_semaphore

    # Create the thread-pool before yielding.
    # max_workers is intentionally small — librosa + ONNX are CPU-bound,
    # so more threads than CPU cores just adds context-switch overhead.
    _executor = ThreadPoolExecutor(
        max_workers=_MAX_CONCURRENT_INFERENCE,
        thread_name_prefix="vaniguard-inference",
    )
    _inference_semaphore = asyncio.Semaphore(_MAX_CONCURRENT_INFERENCE)

    # Load ONNX model in the executor so startup doesn't block the event loop.
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(_executor, init_model)

    yield  # application is running

    # Graceful shutdown: wait for in-flight inference to complete.
    _executor.shutdown(wait=True)


# ── App setup ─────────────────────────────────────────────────────────────────
app = FastAPI(
    title="VaniGuard API",
    description="Real-time AI voice cloning detection for Indian languages.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    # Allow only the configured frontend origin — NOT wildcard.
    # allow_origins=["*"] + allow_credentials=True is forbidden by the CORS spec.
    allow_origins=[_FRONTEND_ORIGIN],
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type", "X-API-Key"],
)

app.include_router(users.router)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _run_inference_sync(audio_bytes: bytes, ext: str) -> dict:
    """
    Pure synchronous function: decode → preprocess → infer.

    This is the ONLY function submitted to the thread-pool executor.
    Everything here is CPU-bound and must not import or call any asyncio
    primitives.

    Returns a plain dict so it can be safely passed back to the async handler.
    """
    # Raises ValueError (too short) or RuntimeError (corrupt audio).
    # Both are caught in the async caller and converted to HTTP errors.
    mel_norm, mel_tensor, duration_s = preprocess_audio(audio_bytes, ext)
    session = get_session()
    prob_ai = run_inference(session, mel_tensor)
    verdict_str, risk_band, risk_css = classify(prob_ai)

    is_ai = "AI-Generated" in verdict_str
    confidence = prob_ai if is_ai else (1.0 - prob_ai)

    return {
        "verdict_str": verdict_str,
        "risk_band": risk_band,
        "risk_css": risk_css,
        "prob_ai": prob_ai,
        "confidence": confidence,
        "duration_s": duration_s,
        "is_ai": is_ai,
    }


def _process_window_sync(pipeline: StreamPipeline, chunk: np.ndarray) -> list:
    """
    Pure synchronous function: feed chunk → get window results.

    Submitted to the thread-pool executor from the WebSocket handler.
    Returns a list of WindowResult dataclass instances.
    """
    return pipeline.write(chunk)


def _flush_pipeline_sync(pipeline: StreamPipeline) -> list:
    """Synchronous flush — also runs in the executor."""
    return pipeline.flush()


# ── /analyze — audio detection ────────────────────────────────────────────────
@app.post("/analyze", tags=["detection"])
async def analyze(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_api_key),
):
    """
    Upload an audio file (WAV/MP3/OGG/FLAC/M4A) for AI voice detection.
    Returns verdict, risk band, probability, and confidence.

    Requires X-API-Key header.
    """
    # ── 1. Validate content-type before reading any bytes ──────────────────
    allowed_types = {
        "audio/wav", "audio/wave", "audio/x-wav",
        "audio/mpeg", "audio/mp3",
        "audio/ogg", "audio/flac",
        "audio/mp4", "audio/m4a", "audio/x-m4a",
        "audio/aac", "audio/webm",
        "application/octet-stream",  # generic — accepted for flexibility
    }
    content_type = (file.content_type or "").split(";")[0].strip().lower()
    if content_type and content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported audio type '{content_type}'.",
        )

    ext = file.filename.rsplit(".", 1)[-1].lower() if file.filename else "wav"
    allowed_exts = {"wav", "mp3", "ogg", "flac", "m4a", "aac", "webm", "opus"}
    if ext not in allowed_exts:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file extension '.{ext}'.",
        )

    # ── 2. Read with a hard size cap — prevent RAM exhaustion ─────────────
    # We read in one shot because the audio must be decoded from raw bytes.
    # The cap prevents malicious oversized uploads from exhausting server RAM.
    audio_bytes = await file.read(_MAX_UPLOAD_BYTES + 1)
    if len(audio_bytes) > _MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Maximum allowed size is {_MAX_UPLOAD_BYTES // (1024*1024)} MB.",
        )

    # ── 3. Dispatch CPU work to the thread-pool — NEVER block event loop ──
    # preprocess_audio (librosa FFT) + run_inference (ONNX) are both
    # CPU-bound.  Running them directly in an async handler would block the
    # entire event loop for the duration of the computation.
    loop = asyncio.get_running_loop()
    async with _inference_semaphore:  # bound concurrent inference jobs
        try:
            result = await loop.run_in_executor(
                _executor,
                functools.partial(_run_inference_sync, audio_bytes, ext),
            )
        except ValueError as exc:
            # Too-short clip or other validation failure — user error.
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(exc),
            )
        except Exception:
            # Do NOT surface internal details (filesystem paths, stack traces)
            # to the client.  Log server-side instead.
            import logging
            logging.getLogger(__name__).exception("Inference failed")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Audio processing failed. Please try again.",
            )

    # ── 4. Map verdict to DB enum ──────────────────────────────────────────
    if result["is_ai"]:
        db_verdict = Verdict.synthetic_clone
    elif "UNCERTAIN" in result["verdict_str"]:
        db_verdict = Verdict.suspicious
    else:
        db_verdict = Verdict.genuine

    # ── 5. Persist to DB (async — stays on the event loop) ────────────────
    repo = ScanRepository(db)
    await repo.create_scan(
        impersonation_risk_score=float(result["prob_ai"] * 100),
        verdict=db_verdict,
        language="English",
        spectral_features={
            "confidence": float(result["confidence"]),
            "duration": float(result["duration_s"]),
        },
    )

    return {
        "verdict": result["verdict_str"],
        "risk_band": result["risk_band"],
        "risk_css": result["risk_css"],
        "prob_ai": round(float(result["prob_ai"]), 4),
        "confidence": round(float(result["confidence"]), 4),
        "confidence_pct": round(float(result["confidence"] * 100), 1),
        "duration_s": round(float(result["duration_s"]), 2),
        "is_ai": result["is_ai"],
        "model_loaded": is_model_loaded(),
    }


# ── /api/scans/history — cursor-paginated history ─────────────────────────────
@app.get("/api/scans/history", tags=["history"])
async def get_scans_history(
    limit: int = Query(default=20, ge=1, le=200),
    cursor: Optional[UUID] = None,
    verdict: Optional[Verdict] = None,
    language: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_api_key),
):
    """Cursor-paginated scan history (newest first). Requires X-API-Key header."""
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
    _: None = Depends(require_api_key),
):
    """Offset-paginated history — backward-compat alias for mobile. Requires X-API-Key header."""
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
async def get_stats(
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_api_key),
):
    """Aggregate statistics across all scans. Requires X-API-Key header."""
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


# ── /api/health — health check (PUBLIC — no auth required) ───────────────────
@app.get("/api/health", tags=["health"])
async def health_check():
    """
    Server health, model status, and uptime.

    Intentionally unauthenticated: load-balancers and uptime monitors need
    to reach this endpoint without credentials.

    NOTE: model_error is sanitized — no filesystem paths are returned.
    """
    raw_error = get_model_error()
    # Never expose internal paths or exception details to clients.
    safe_error: Optional[str] = None
    if raw_error:
        safe_error = "Model unavailable" if "not found" in raw_error.lower() else "Model load failed"

    return {
        "status": "healthy" if is_model_loaded() else "degraded",
        "model_loaded": is_model_loaded(),
        "model_error": safe_error,
        "version": "1.0.0",
        "uptime_s": round(get_uptime(), 1),
    }


# ── /stream — WebSocket live monitoring ──────────────────────────────────────
@app.websocket("/stream")
async def stream(websocket: WebSocket):
    """
    WebSocket endpoint for real-time live monitoring.

    Authentication: the client must send 'X-API-Key: <key>' as the first
    text message immediately after the connection opens.  This avoids
    putting the key in the URL (which gets logged by proxies).

    Audio: client sends raw PCM float32 chunks at 16 kHz (mono).
    Server responds with JSON per analysis window.

    CPU-heavy work (librosa + ONNX) is dispatched to the thread-pool
    executor so the event loop is never blocked between WebSocket frames.
    See HIGH-08 in the audit report.
    """
    # ── 1. Accept connection so we can exchange the auth message ──────────
    await websocket.accept()

    # ── 2. Authenticate via first text message ────────────────────────────
    # We avoid query-param auth because URLs are routinely logged by
    # load-balancers, proxies, and browser history.
    try:
        auth_msg = await asyncio.wait_for(websocket.receive_text(), timeout=10.0)
    except asyncio.TimeoutError:
        await websocket.close(code=4008, reason="Authentication timeout.")
        return
    except WebSocketDisconnect:
        return

    import hmac as _hmac
    import os as _os
    _api_key = _os.getenv("VANIGUARD_API_KEY")

    if not _api_key or not _hmac.compare_digest(auth_msg, _api_key):
        await websocket.close(code=4003, reason="Invalid or missing API key.")
        return

    # ── 3. Set up inference pipeline for this connection ──────────────────
    session = get_session()
    sp = StreamPipeline(session=session)
    engine = RiskEngine()
    engine.reset()

    loop = asyncio.get_running_loop()

    try:
        while True:
            # Receive raw bytes from client.
            data = await websocket.receive_bytes()

            # Reject oversized messages to prevent unbounded memory allocation.
            if len(data) > _MAX_WS_MSG_BYTES:
                await websocket.close(
                    code=4009,
                    reason=f"Message too large. Max {_MAX_WS_MSG_BYTES} bytes.",
                )
                return

            # Validate the payload is a valid float32 PCM buffer.
            if len(data) % 4 != 0:
                # float32 is always 4 bytes — odd size means corrupt frame.
                await websocket.close(code=4010, reason="Malformed PCM data.")
                return

            chunk = np.frombuffer(data, dtype=np.float32)

            # ── Dispatch CPU-bound work to the thread-pool executor ────────
            # librosa (mel-spectrogram) + ONNX inference must NOT run on the
            # event loop — they are synchronous and CPU-intensive.
            # Using the semaphore prevents unbounded concurrent inference from
            # saturating all CPU cores when many connections are open.
            async with _inference_semaphore:
                results = await loop.run_in_executor(
                    _executor,
                    functools.partial(_process_window_sync, sp, chunk),
                )

            # Send results back over the WebSocket (async, on event loop).
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
        # Client disconnected cleanly — flush remaining buffer in executor
        # to avoid wasting CPU cycles on results we can't send.
        # We still run flush to properly reset pipeline state.
        try:
            await loop.run_in_executor(
                _executor,
                functools.partial(_flush_pipeline_sync, sp),
            )
        except Exception:
            pass  # Best-effort flush — ignore errors on disconnect.

    except Exception:
        # Unexpected processing error — close cleanly, don't expose internals.
        import logging
        logging.getLogger(__name__).exception("WebSocket stream error")
        try:
            await websocket.close(code=1011, reason="Internal server error.")
        except Exception:
            pass
