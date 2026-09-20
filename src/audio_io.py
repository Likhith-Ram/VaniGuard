"""
src/audio_io.py — Audio decoding: bytes → float32 PCM numpy array.

Zero Streamlit imports. Strategy:
  A (preferred) : miniaudio — native C decoder, handles MP3/WAV/FLAC/OGG/M4A.
  B (fallback)  : soundfile + librosa.resample — WAV/FLAC/OGG only.
"""

import io

import librosa
import numpy as np
import soundfile as sf

from src.config import SAMPLE_RATE

# Optional miniaudio — present when installed, absent in some CI envs.
try:
    import miniaudio
    _MINIAUDIO_OK: bool = True
except ImportError:
    _MINIAUDIO_OK = False


def _decode_audio_bytes(audio_bytes: bytes, ext: str) -> np.ndarray:
    """
    Decode raw upload bytes to a float32 mono PCM array at SAMPLE_RATE.

    Parameters
    ----------
    audio_bytes : bytes
        Raw audio file content (as read from an uploaded file).
    ext : str
        File extension without dot, lower-case (e.g. ``"wav"``, ``"mp3"``).

    Returns
    -------
    np.ndarray
        1-D float32 array of PCM samples, resampled to SAMPLE_RATE.

    Raises
    ------
    RuntimeError
        If decoding fails for any reason, or if MP3/M4A is requested
        but miniaudio is unavailable.
    """
    if _MINIAUDIO_OK:
        # Strategy A — miniaudio (all formats, no ffmpeg)
        try:
            decoded = miniaudio.decode(
                audio_bytes,
                output_format=miniaudio.SampleFormat.FLOAT32,
                nchannels=1,
                sample_rate=SAMPLE_RATE,
            )
            return np.frombuffer(decoded.samples, dtype=np.float32).copy()
        except miniaudio.DecodeError as exc:
            raise RuntimeError(
                f"miniaudio could not decode the {ext.upper()} file: {exc}. "
                "Try converting to WAV or FLAC."
            ) from exc
        except Exception as exc:
            raise RuntimeError(f"Decode error: {exc}") from exc
    else:
        # Strategy B — soundfile fallback (WAV/FLAC/OGG only)
        if ext in ("mp3", "m4a"):
            raise RuntimeError(
                f"Cannot decode {ext.upper()} files — miniaudio is not installed. "
                "Please upload a WAV or FLAC file, or run: pip install miniaudio"
            )
        try:
            data, native_sr = sf.read(
                io.BytesIO(audio_bytes), dtype="float32", always_2d=False
            )
        except Exception as exc:
            raise RuntimeError(
                f"soundfile could not decode the {ext.upper()} file: {exc}"
            ) from exc
        if data.ndim > 1:
            data = data.mean(axis=1)  # stereo → mono
        if native_sr != SAMPLE_RATE:
            try:
                data = librosa.resample(data, orig_sr=native_sr, target_sr=SAMPLE_RATE)
            except Exception as exc:
                raise RuntimeError(
                    f"Failed to resample from {native_sr} Hz to {SAMPLE_RATE} Hz: {exc}"
                ) from exc
        return data
