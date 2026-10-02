"""
src/risk_engine.py — Rolling-window risk fusion engine.

Ingests per-window impersonation probabilities from :class:`StreamPipeline`
and maintains a stateful risk level that escalates only when suspicious
scores are **sustained**, preventing single-spike false alarms.

State machine
-------------
    Green  → default / low risk; no sustained suspicious activity.
    Amber  → probabilities in [0.50, 0.75] sustained for ≥ 2 consecutive windows.
    Red    → probabilities above 0.75 sustained for ≥ 3 consecutive windows.

Higher-severity states take precedence: a run that qualifies for both
Amber *and* Red is classified Red.

Usage::

    engine = RiskEngine()
    for result in stream_pipeline.write(chunk):
        engine.ingest(result.prob_ai)
    state = engine.get_state()
    print(state.level, state.confidence)

History buffer design
---------------------
The rolling history uses :class:`collections.deque` with ``maxlen`` set to
``history_size``.  This replaces the previous ``list[-N:]`` slice pattern
which created a new list object every time the history overflowed (every 5
windows by default).  ``deque.append`` is O(1) and auto-evicts the oldest
element when full — no slice allocation needed.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import List

from src import config


class RiskLevel(Enum):
    """Enumerated risk levels, ordered by severity."""

    GREEN = "GREEN"
    AMBER = "AMBER"
    RED = "RED"


@dataclass(frozen=True)
class RiskState:
    """
    Immutable snapshot of the engine's current assessment.

    Attributes
    ----------
    level : RiskLevel
        Current risk level (GREEN / AMBER / RED).
    confidence : float
        Smoothed confidence score — mean of the rolling history, ∈ [0, 1].
        When history is empty this is 0.0.
    consecutive_amber : int
        Length of the current unbroken run of windows with prob ∈ [0.50, 1.0].
    consecutive_red : int
        Length of the current unbroken run of windows with prob > 0.75.
    window_count : int
        Total number of windows ingested since last reset.
    """

    level: RiskLevel
    confidence: float
    consecutive_amber: int
    consecutive_red: int
    window_count: int


# ── Escalation thresholds ─────────────────────────────────────────────────
_AMBER_THRESHOLD: float = config.EER_THRESHOLD
_RED_THRESHOLD: float = config.THRESH_HIGH
_AMBER_SUSTAIN: int = 2   # consecutive windows required to reach Amber
_RED_SUSTAIN: int = 3     # consecutive windows required to reach Red
_HISTORY_SIZE: int = 5    # rolling window length


@dataclass
class RiskEngine:
    """
    Stateful risk fusion engine with rolling history and escalation logic.

    Parameters
    ----------
    history_size : int
        Maximum number of recent probabilities to retain.  Default 5.
    amber_threshold : float
        Minimum prob to count toward an Amber run.  Default 0.50.
    red_threshold : float
        Minimum prob to count toward a Red run.  Default 0.75.
    amber_sustain : int
        Consecutive windows at/above *amber_threshold* to trigger Amber.
    red_sustain : int
        Consecutive windows above *red_threshold* to trigger Red.
    """

    history_size: int = _HISTORY_SIZE
    amber_threshold: float = _AMBER_THRESHOLD
    red_threshold: float = _RED_THRESHOLD
    amber_sustain: int = _AMBER_SUSTAIN
    red_sustain: int = _RED_SUSTAIN

    # ── internal state ────────────────────────────────────────────────────
    # deque with maxlen enforces the rolling window in O(1) — no list slice.
    _history: deque = field(init=False)
    _consecutive_amber: int = field(default=0, init=False)
    _consecutive_red: int = field(default=0, init=False)
    _window_count: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        # maxlen=history_size means deque auto-evicts the oldest entry when
        # a new one is appended and the buffer is full.  No manual slicing.
        self._history = deque(maxlen=self.history_size)

    # ── public API ────────────────────────────────────────────────────────

    def ingest(self, prob_ai: float) -> RiskState:
        """
        Record a new window probability and return the updated risk state.

        Parameters
        ----------
        prob_ai : float
            P(AI-generated) for the latest window, ∈ [0, 1].

        Returns
        -------
        RiskState
            Snapshot of the engine's assessment *after* incorporating this window.
        """
        prob_ai = max(0.0, min(1.0, prob_ai))  # defensive clamp

        # O(1) append — deque auto-evicts the oldest entry when maxlen is hit.
        self._history.append(prob_ai)

        self._window_count += 1

        # Update consecutive counters
        if prob_ai >= self.amber_threshold:
            self._consecutive_amber += 1
        else:
            self._consecutive_amber = 0

        if prob_ai > self.red_threshold:
            self._consecutive_red += 1
        else:
            self._consecutive_red = 0

        return self.get_state()

    def get_state(self) -> RiskState:
        """
        Return the current risk state without ingesting a new value.

        Returns
        -------
        RiskState
        """
        level = self._evaluate_level()
        # sum() and len() both work on deque in O(N) — acceptable for N ≤ 5.
        confidence = (
            sum(self._history) / len(self._history) if self._history else 0.0
        )
        return RiskState(
            level=level,
            confidence=round(confidence, 6),
            consecutive_amber=self._consecutive_amber,
            consecutive_red=self._consecutive_red,
            window_count=self._window_count,
        )

    def reset(self) -> None:
        """Clear all history and counters for a new call session."""
        self._history.clear()
        self._consecutive_amber = 0
        self._consecutive_red = 0
        self._window_count = 0

    # ── internal helpers ──────────────────────────────────────────────────

    def _evaluate_level(self) -> RiskLevel:
        """Determine the risk level from current consecutive counters."""
        # Red takes priority over Amber
        if self._consecutive_red >= self.red_sustain:
            return RiskLevel.RED
        if self._consecutive_amber >= self.amber_sustain:
            return RiskLevel.AMBER
        return RiskLevel.GREEN
