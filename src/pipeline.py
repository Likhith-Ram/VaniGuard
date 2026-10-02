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

Buffer implementation note
--------------------------
The internal buffer uses :class:`collections.deque` instead of a growing
numpy array.  ``np.concatenate`` allocates a brand-new array on every
``write()`` call, producing O(total_samples) garbage-collection pressure
over a long stream.  ``deque.extend`` is O(chunk_size) with no
reallocation, and ``popleft`` is O(1).  Window extraction creates a single
numpy array only when a full window is ready for inference.
"""

from __future__ import annotations

import itertools
from collections import deque
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

    Buffer design
    -------------
    The buffer is a :class:`collections.deque` of float32 scalars rather
    than a growing numpy array.  This eliminates the O(N) allocation cost
    of ``np.concatenate`` that would otherwise fire on every ``write()``
    call (potentially hundreds of times per minute during a live stream).

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
    # deque of float32 scalars — O(1) extend/popleft, no reallocation.
    _buffer: deque = field(init=False)
    _window_count: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        self._buffer = deque()

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

        # O(len(chunk)) extend — no new array is allocated for the buffer.
        self._buffer.extend(chunk)

        results: List[WindowResult] = []
        while len(self._buffer) >= self.window_samples:
            # Extract a contiguous window as a fresh numpy array for inference.
            # islice is O(window_samples) but only fires once per hop (≈ 1 s).
            window = np.fromiter(
                itertools.islice(self._buffer, self.window_samples),
                dtype=np.float32,
                count=self.window_samples,
            )
            result = self._process_window(window)
            results.append(result)

            # Slide the buffer forward by hop_samples.
            # deque.popleft() is O(1); total cost is O(hop_samples) per window.
            for _ in range(self.hop_samples):
                self._buffer.popleft()

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
            window = np.fromiter(
                itertools.islice(self._buffer, self.window_samples),
                dtype=np.float32,
                count=self.window_samples,
            )
            results.append(self._process_window(window))
            for _ in range(self.hop_samples):
                if self._buffer:
                    self._buffer.popleft()
        return results

    def reset(self) -> None:
        """Clear the internal buffer and reset window counter."""
        self._buffer = deque()
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
