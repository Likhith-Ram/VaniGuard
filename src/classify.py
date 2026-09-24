"""
src/classify.py — Map P(AI-generated) probability to verdict + risk band.

Zero Streamlit imports. Pure function with no side effects.

Supports two modes:
  1. **Manual thresholds** (default, backward-compatible):
     Uses the hard-coded values from ``config.py``.
  2. **EER-calibrated thresholds** (opt-in):
     Pass a ``CalibratedThresholds`` from ``src.metrics.calibrate_thresholds``
     to ``classify()`` to use data-driven thresholds instead.

Manual thresholds (all inclusive lower bound):
    P(AI) >= THRESH_HIGH      → "AI-Generated",  "HIGH RISK",   "risk-high"
    P(AI) >= THRESH_SUS       → "AI-Generated",  "SUSPICIOUS",  "risk-sus"
    P(AI) >= THRESH_UNCERTAIN → "UNCERTAIN",      "UNCERTAIN",   "risk-uncertain"
    P(AI) <  THRESH_UNCERTAIN → "Human",          "LOW RISK",    "risk-low"
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from src.config import THRESH_HIGH, THRESH_SUS, THRESH_UNCERTAIN

if TYPE_CHECKING:
    from src.metrics import CalibratedThresholds


def classify(
    prob_ai: float,
    calibrated: Optional[CalibratedThresholds] = None,
) -> tuple[str, str, str]:
    """
    Classify an AI-probability score into a verdict, risk band, and CSS class.

    Parameters
    ----------
    prob_ai : float
        P(AI-generated) in [0.0, 1.0] as returned by ``run_inference``.
    calibrated : CalibratedThresholds, optional
        If provided, uses EER-calibrated thresholds instead of the
        hard-coded defaults.  This reduces false alarms on real human
        speech by placing thresholds at data-driven operating points.

    Returns
    -------
    verdict : str
        Human-readable verdict label (e.g. ``"AI-Generated"``).
    risk_band : str
        Full risk band description (e.g. ``"HIGH RISK — very likely AI-generated"``).
    risk_css : str
        CSS class name for styling (e.g. ``"risk-high"``).
    """
    if calibrated is not None:
        t_high = calibrated.high
        t_sus = calibrated.suspicious
        t_unc = calibrated.uncertain
    else:
        t_high = THRESH_HIGH
        t_sus = THRESH_SUS
        t_unc = THRESH_UNCERTAIN

    if prob_ai >= t_high:
        return "AI-Generated", "HIGH RISK — very likely AI-generated", "risk-high"
    elif prob_ai >= t_sus:
        return "AI-Generated", "SUSPICIOUS — possibly AI-generated", "risk-sus"
    elif prob_ai >= t_unc:
        return "UNCERTAIN", "UNCERTAIN — manual review advised", "risk-uncertain"
    else:
        return "Human", "LOW RISK — likely human speech", "risk-low"
