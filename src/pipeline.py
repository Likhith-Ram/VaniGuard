"""
src/pipeline.py — Public façade re-exporting all pipeline symbols.

Import from here for a stable API surface:

    from src.pipeline import (
        _decode_audio_bytes,
        preprocess_audio,
        load_model,
        run_inference,
        classify,
        load_history,
        save_to_history,
        clear_history,
    )

The internal split (audio_io / features / model / classify / history) is an
implementation detail — consumers only need to know this module.

Streaming support
-----------------
The :class:`StreamPipeline` class enables real-time, chunk-based inference.
Feed it arbitrary-length PCM chunks via :meth:`write`; it maintains an
internal ring buffer and slides a 4-second window with a 1-second hop,
yielding one prediction per hop.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional

import numpy as np

from src.audio_io import _decode_audio_bytes  # noqa: F401
from src.classify import classify              # noqa: F401
from src.config import (                      # noqa: F401
    DURATION,
    HOP_LENGTH,
    HISTORY_COLS,
    HISTORY_FILE,
    MIN_DURATION,
    MODEL_PATH,
    N_FFT,
    N_MELS,
    SAMPLE_RATE,
    STREAM_HOP_SAMPLES,
    STREAM_HOP_S,
    STREAM_WINDOW_SAMPLES,
    STREAM_WINDOW_S,
    THRESH_HIGH,
    THRESH_SUS,
    THRESH_UNCERTAIN,
)
from src.features import preprocess_audio, preprocess_audio_array  # noqa: F401
from src.history import (                      # noqa: F401
    clear_history,
    load_history,
    save_to_history,
)
from src.model import (                        # noqa: F401
    get_cached_session,
    load_model,
    run_inference,
)


# ── Streaming pipeline ────────────────────────────────────────────────────


@dataclass
class WindowResult:
    """Result of inference on a single sliding window."""

    window_index: int
    """0-based index of this window among all windows emitted so far."""

    prob_ai: float
    """P(AI-generated) ∈ [0, 1] for this window."""

    verdict: str
    """Human-readable verdict (e.g. ``"AI-Generated"``, ``"Human"``)."""

    risk_band: str
    """Full risk-band description."""

    risk_css: str
    """CSS class name for UI styling."""


@dataclass
class StreamPipeline:
    """
    Stateful streaming pipeline with ring-buffer and sliding window.

    Maintains an internal buffer of raw PCM samples (16 kHz, 16-bit mono,
    stored as float32) and slides a **4-second window** with a **1-second
    hop** over incoming data.

    Usage::

        sp = StreamPipeline()
        # or bring your own ONNX session:
        sp = StreamPipeline(session=my_session)

        for chunk in audio_source:
            results = sp.write(chunk)
            for r in results:
                print(r.window_index, r.prob_ai, r.verdict)

        # flush any remaining full window at the end:
        results = sp.flush()

    Parameters
    ----------
    session : optional
        Pre-loaded ONNX session.  When *None* (default), inference runs
        in random-fallback mode (same as ``run_inference(None, …)``).
    window_samples : int
        Number of samples per analysis window.  Default 64 000 (4 s @ 16 kHz).
    hop_samples : int
        Number of samples to advance between windows.  Default 16 000 (1 s).
    """

    session: Optional[Any] = None
    window_samples: int = STREAM_WINDOW_SAMPLES
    hop_samples: int = STREAM_HOP_SAMPLES

    # ── internal state (not constructor args) ─────────────────────────────
    _buffer: np.ndarray = field(init=False)
    _write_pos: int = field(default=0, init=False)
    _window_count: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        # Pre-allocate a ring buffer large enough for one full window.
        # We grow it dynamically when more data arrives than fits.
        self._buffer = np.empty(0, dtype=np.float32)

    # ── public API ────────────────────────────────────────────────────────

    def write(self, chunk: np.ndarray) -> List[WindowResult]:
        """
        Append a chunk of PCM samples and run inference on any new full windows.

        Parameters
        ----------
        chunk : np.ndarray
            1-D float32 PCM samples at ``SAMPLE_RATE`` Hz.

        Returns
        -------
        list[WindowResult]
            Zero or more results, one per window that became available.
        """
        chunk = np.asarray(chunk, dtype=np.float32).ravel()
        self._buffer = np.concatenate([self._buffer, chunk])

        results: List[WindowResult] = []
        while len(self._buffer) >= self.window_samples:
            window = self._buffer[: self.window_samples]
            result = self._process_window(window)
            results.append(result)
            # Slide forward by hop_samples
            self._buffer = self._buffer[self.hop_samples:]
        return results

    def flush(self) -> List[WindowResult]:
        """
        Process any remaining samples that form a complete window.

        Call this after the last :meth:`write` to ensure no trailing full
        window is left unprocessed.  Partial windows (< ``window_samples``)
        are discarded.

        Returns
        -------
        list[WindowResult]
            Zero or one result.
        """
        results: List[WindowResult] = []
        if len(self._buffer) >= self.window_samples:
            window = self._buffer[: self.window_samples]
            results.append(self._process_window(window))
            self._buffer = self._buffer[self.hop_samples:]
        return results

    def reset(self) -> None:
        """Clear the internal buffer and reset window counter."""
        self._buffer = np.empty(0, dtype=np.float32)
        self._write_pos = 0
        self._window_count = 0

    @property
    def total_windows(self) -> int:
        """Number of windows processed so far."""
        return self._window_count

    @property
    def buffered_samples(self) -> int:
        """Number of PCM samples currently in the ring buffer."""
        return len(self._buffer)

    # ── internal helpers ──────────────────────────────────────────────────

    def _process_window(self, window: np.ndarray) -> WindowResult:
        """Extract features, run inference, classify."""
        _, mel_tensor, _ = preprocess_audio_array(
            window, target_duration=STREAM_WINDOW_S
        )
        prob_ai = run_inference(self.session, mel_tensor)
        verdict, risk_band, risk_css = classify(prob_ai)
        idx = self._window_count
        self._window_count += 1
        return WindowResult(
            window_index=idx,
            prob_ai=prob_ai,
            verdict=verdict,
            risk_band=risk_band,
            risk_css=risk_css,
        )
