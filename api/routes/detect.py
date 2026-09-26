"""
api/routes/detect.py — Audio detection endpoint.

POST /api/detect
    Accepts an audio file upload, runs it through the full VaniGuard
    pipeline (decode → preprocess → ONNX inference → classify),
    saves the result to history, and returns the verdict.
"""

from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, UploadFile

from api.database import save_detection
from api.dependencies import get_session, is_model_loaded
from api.schemas import DetectionResult
from src.classify import classify
from src.features import preprocess_audio
from src.model import run_inference

router = APIRouter(prefix="/api", tags=["detection"])

# Maximum upload size: 50 MB
_MAX_UPLOAD_BYTES = 50 * 1024 * 1024

# Allowed audio extensions
_ALLOWED_EXTENSIONS = {"wav", "mp3", "ogg", "flac", "m4a"}


def _extract_extension(filename: str | None) -> str:
    """Extract and validate the file extension."""
    if not filename:
        raise HTTPException(
            status_code=400,
            detail="Filename is required to determine audio format.",
        )
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in _ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported file format: .{ext}. "
                f"Allowed: {', '.join(sorted(_ALLOWED_EXTENSIONS))}"
            ),
        )
    return ext


def _risk_level_from_css(risk_css: str) -> str:
    """Convert CSS class name to a short risk level string."""
    mapping = {
        "risk-high": "high",
        "risk-sus": "suspicious",
        "risk-uncertain": "uncertain",
        "risk-low": "low",
    }
    return mapping.get(risk_css, "unknown")


@router.post(
    "/detect",
    response_model=DetectionResult,
    summary="Detect AI-generated voice",
    description="Upload an audio file to determine whether the voice is human or AI-generated.",
)
async def detect_audio(
    file: UploadFile = File(..., description="Audio file (WAV, MP3, OGG, FLAC, M4A)"),
) -> DetectionResult:
    """Run the full VaniGuard detection pipeline on an uploaded audio file."""

    # 1. Validate extension
    ext = _extract_extension(file.filename)

    # 2. Read bytes and validate size
    audio_bytes = await file.read()
    if len(audio_bytes) > _MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=(
                f"File too large ({len(audio_bytes) / 1024 / 1024:.1f} MB). "
                f"Maximum allowed: {_MAX_UPLOAD_BYTES / 1024 / 1024:.0f} MB."
            ),
        )
    if len(audio_bytes) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    # 3. Run pipeline
    try:
        mel_norm, mel_tensor, duration_s = preprocess_audio(audio_bytes, ext)
        session = get_session()
        prob_ai = run_inference(session, mel_tensor)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error processing audio: {exc}",
        )

    # 4. Classify
    verdict, risk_band, risk_css = classify(prob_ai)
    is_ai = "AI-Generated" in verdict
    confidence = prob_ai if is_ai else (1.0 - prob_ai)
    confidence_pct = confidence * 100

    # 5. Save to database
    try:
        save_detection(
            filename=file.filename or "unknown",
            verdict=verdict,
            confidence_pct=confidence_pct,
            risk_band=risk_band,
            probability=prob_ai,
        )
    except Exception:
        # Don't fail the detection if history save fails
        pass

    # 6. Return result
    return DetectionResult(
        filename=file.filename or "unknown",
        verdict=verdict,
        probability=round(prob_ai, 4),
        confidence_pct=round(confidence_pct, 1),
        risk_band=risk_band,
        risk_level=_risk_level_from_css(risk_css),
        duration_s=round(duration_s, 2),
        is_ai=is_ai,
        model_loaded=is_model_loaded(),
    )
