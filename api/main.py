"""
api/main.py - FastAPI entry point for VaniGuard
"""
from fastapi import FastAPI, UploadFile, File, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import asyncio
import numpy as np

from src.pipeline import (
    _decode_audio_bytes,
    preprocess_audio,
    load_model,
    run_inference,
    classify,
    load_history,
    save_to_history,
    StreamPipeline
)
from src.risk_engine import RiskEngine

app = FastAPI(title="VaniGuard API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load model globally on startup (or lazy load)
session, _ = load_model()

from typing import Optional
from uuid import UUID
from fastapi import Depends
from api.core.database import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from api.repositories.scan_repository import ScanRepository
from api.models.models import Verdict

@app.post("/analyze")
async def analyze(file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    """Analyze a complete audio file in batch."""
    audio_bytes = await file.read()
    ext = file.filename.rsplit(".", 1)[-1].lower() if file.filename else "wav"
    
    # Process
    mel_norm, mel_tensor, duration_s = preprocess_audio(audio_bytes, ext)
    prob_ai = run_inference(session, mel_tensor)
    verdict_str, risk_band, risk_css = classify(prob_ai)
    
    is_ai = "AI-Generated" in verdict_str
    confidence = prob_ai if is_ai else (1.0 - prob_ai)
    
    # Map to DB enum
    if "AI-Generated" in verdict_str:
        db_verdict = Verdict.synthetic_clone
    elif "UNCERTAIN" in verdict_str:
        db_verdict = Verdict.suspicious
    else:
        db_verdict = Verdict.genuine

    # Save to history atomically using repository
    repo = ScanRepository(db)
    await repo.create_scan(
        impersonation_risk_score=float(prob_ai * 100),
        verdict=db_verdict,
        language="English", # Default for now
        spectral_features={"confidence": float(confidence), "duration": float(duration_s)}
    )
    
    return {
        "verdict": verdict_str,
        "risk_band": risk_band,
        "risk_css": risk_css,
        "prob_ai": float(prob_ai),
        "confidence": float(confidence),
        "duration_s": float(duration_s)
    }

@app.get("/api/scans/history")
async def get_scans_history(
    limit: int = 20,
    cursor: Optional[UUID] = None,
    verdict: Optional[Verdict] = None,
    language: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """Get the history of analyzed files with cursor-based pagination."""
    repo = ScanRepository(db)
    scans, next_cursor = await repo.get_history(
        limit=limit,
        cursor=cursor,
        verdict=verdict,
        language=language
    )
    
    return {
        "items": [
            {
                "id": scan.id,
                "language": scan.language,
                "impersonation_risk_score": scan.impersonation_risk_score,
                "verdict": scan.verdict,
                "scanned_at": scan.scanned_at
            }
            for scan in scans
        ],
        "next_cursor": next_cursor
    }

@app.websocket("/stream")
async def stream(websocket: WebSocket):
    """
    WebSocket endpoint for real-time live monitoring.
    Client sends raw binary chunks (PCM float32, 16kHz, mono).
    Server responds with JSON containing risk engine status per window.
    """
    await websocket.accept()
    
    sp = StreamPipeline(session=session)
    engine = RiskEngine()
    engine.reset()
    
    try:
        while True:
            data = await websocket.receive_bytes()
            # Convert bytes to numpy float32 array
            # We expect the client to send raw PCM float32 bytes at 16kHz.
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
                    "status_confidence": float(state.confidence)
                })
    except WebSocketDisconnect:
        print("WebSocket client disconnected")
        # Flush the remainder
        results = sp.flush()
        for r in results:
            state = engine.ingest(r.prob_ai)
            # Not sending it since socket is dead, but processing finishes
