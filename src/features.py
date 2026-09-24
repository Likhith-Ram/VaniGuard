"""
src/features.py — Mel-spectrogram feature extraction pipeline.

Zero Streamlit imports.

Pipeline
--------
Stage 1  decode bytes → float32 PCM          (delegated to audio_io)
Stage 2  validate duration ≥ MIN_DURATION
Stage 3  trim / zero-pad to DURATION seconds
Stage 4  Log-Mel Spectrogram  (N_MELS bands, N_FFT, HOP_LENGTH)
Stage 5  min-max normalise to [0, 1]
Stage 6  reshape → (1, N_MELS, T, 1) float32 for ONNX
"""

import numpy as np
import librosa

from src.audio_io import _decode_audio_bytes
from src.config import (
    SAMPLE_RATE, DURATION, N_MELS, N_FFT, HOP_LENGTH, MIN_DURATION
)


def preprocess_audio(
    audio_bytes: bytes, ext: str
) -> tuple[np.ndarray, np.ndarray, float]:
    """
    Full in-memory preprocessing pipeline.

    Parameters
    ----------
    audio_bytes : bytes
        Raw audio file bytes.
    ext : str
        File extension without dot, lower-case.

    Returns
    -------
    mel_norm   : np.ndarray  shape (N_MELS, T)          — for display
    mel_tensor : np.ndarray  shape (1, N_MELS, T, 1) float32 — for ONNX
    duration_s : float       actual clip length before padding/trimming

    Raises
    ------
    ValueError   if the clip is shorter than MIN_DURATION seconds.
    RuntimeError if audio decoding fails.
    """
    # Stage 1 — decode
    y: np.ndarray = _decode_audio_bytes(audio_bytes, ext)

    # Stage 2 — validate
    duration_s: float = len(y) / SAMPLE_RATE
    if duration_s < MIN_DURATION:
        raise ValueError(
            f"Audio clip is too short ({duration_s:.2f} s). "
            f"Please upload a clip that is at least {MIN_DURATION} s long."
        )

    # Stage 3 — trim / zero-pad
    target_len: int = int(SAMPLE_RATE * DURATION)
    if len(y) > target_len:
        y = y[:target_len]
    else:
        y = np.pad(y, (0, target_len - len(y)))

    # Stage 4 — Log-Mel Spectrogram
    mel: np.ndarray = librosa.feature.melspectrogram(
        y=y, sr=SAMPLE_RATE, n_fft=N_FFT, hop_length=HOP_LENGTH, n_mels=N_MELS
    )
    mel_db: np.ndarray = librosa.power_to_db(mel, ref=np.max)

    # Stage 5 — min-max normalise to [0, 1]
    lo: float = float(mel_db.min())
    hi: float = float(mel_db.max())
    mel_norm: np.ndarray = (mel_db - lo) / (hi - lo) if hi > lo else (mel_db - lo)

    # Stage 6 — reshape for ONNX: (N_MELS, T) → (1, N_MELS, T, 1)
    mel_tensor: np.ndarray = mel_norm.reshape(
        1, N_MELS, mel_norm.shape[1], 1
    ).astype(np.float32)

    return mel_norm, mel_tensor, duration_s


def preprocess_audio_array(
    y: np.ndarray,
    target_duration: float = DURATION,
) -> tuple[np.ndarray, np.ndarray, float]:
    """
    Feature extraction from an in-memory float32 PCM array.

    Identical to :func:`preprocess_audio` stages 2–6 but skips the byte-decoding
    step, accepting a raw numpy array instead.  Used by :class:`StreamPipeline`.

    Parameters
    ----------
    y : np.ndarray
        1-D float32 PCM samples at ``SAMPLE_RATE`` Hz.
    target_duration : float
        Clip length in seconds to trim/pad to.  Defaults to ``DURATION`` for
        backward compat; the streaming pipeline passes ``STREAM_WINDOW_S``.

    Returns
    -------
    mel_norm   : np.ndarray  shape (N_MELS, T)          — for display
    mel_tensor : np.ndarray  shape (1, N_MELS, T, 1) float32 — for ONNX
    duration_s : float       actual clip length before padding/trimming
    """
    duration_s: float = len(y) / SAMPLE_RATE

    # Trim / zero-pad
    target_len: int = int(SAMPLE_RATE * target_duration)
    if len(y) > target_len:
        y = y[:target_len]
    else:
        y = np.pad(y, (0, max(0, target_len - len(y))))

    # Log-Mel Spectrogram
    mel: np.ndarray = librosa.feature.melspectrogram(
        y=y, sr=SAMPLE_RATE, n_fft=N_FFT, hop_length=HOP_LENGTH, n_mels=N_MELS
    )
    mel_db: np.ndarray = librosa.power_to_db(mel, ref=np.max)

    # Min-max normalise to [0, 1]
    lo: float = float(mel_db.min())
    hi: float = float(mel_db.max())
    mel_norm: np.ndarray = (mel_db - lo) / (hi - lo) if hi > lo else (mel_db - lo)

    # Reshape for ONNX: (N_MELS, T) → (1, N_MELS, T, 1)
    mel_tensor: np.ndarray = mel_norm.reshape(
        1, N_MELS, mel_norm.shape[1], 1
    ).astype(np.float32)

    return mel_norm, mel_tensor, duration_s
