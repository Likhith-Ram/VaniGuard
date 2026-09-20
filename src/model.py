"""
src/model.py — ONNX model loading and inference.

Zero Streamlit imports.

Design note: `session` is passed as an explicit argument to `run_inference`
rather than being a module-level global. This makes the function easily
testable (no need to monkey-patch module state) and avoids hidden coupling
between test setup and global state.
"""

from __future__ import annotations

import os
from typing import Any, Optional

import numpy as np

from src.config import MODEL_PATH


def load_model(
    model_path: str = MODEL_PATH,
) -> tuple[Optional[Any], Optional[str]]:
    """
    Load the ONNX inference session from disk.

    Parameters
    ----------
    model_path : str
        Path to the ``.onnx`` file.  Defaults to ``config.MODEL_PATH``.

    Returns
    -------
    (session, error_message)
        ``session`` is an ``onnxruntime.InferenceSession`` on success,
        ``None`` on failure.  ``error_message`` is ``None`` on success,
        a human-readable string on failure.
    """
    try:
        import onnxruntime as ort  # lazy import — optional in test environments
    except ImportError:
        return None, "onnxruntime is not installed"

    if not os.path.exists(model_path):
        return None, f"Model file not found: {model_path}"
    try:
        sess = ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])
        _ = sess.get_inputs()[0].name   # validate graph is readable
        return sess, None
    except Exception as exc:
        return None, str(exc)


def run_inference(session: Any, mel_tensor: np.ndarray) -> float:
    """
    Run ONNX inference and return P(AI-generated) clamped to [0, 1].

    Parameters
    ----------
    session : onnxruntime.InferenceSession or None
        Loaded ONNX session.  When ``None`` a random value in [0, 1]
        is returned as a fallback (demo / model-unavailable mode).
    mel_tensor : np.ndarray
        Shape ``(1, N_MELS, T, 1)``, dtype float32.

    Returns
    -------
    float
        P(AI-generated) in [0.0, 1.0].
    """
    if session is None:
        # Model unavailable — random fallback (clearly disclosed in UI)
        return float(np.random.uniform(0.0, 1.0))

    input_name: str = session.get_inputs()[0].name
    output = session.run(None, {input_name: mel_tensor})

    raw = output[0]
    # Handle output shapes: (1,1), (1,), or scalar-like
    prob: float = float(np.asarray(raw).flatten()[0])
    return max(0.0, min(1.0, prob))   # clamp to [0, 1]
