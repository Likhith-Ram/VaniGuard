"""
src/classify.py — Map P(AI-generated) probability to verdict + risk band.

Zero Streamlit imports. Pure function with no side effects.

Thresholds (all inclusive lower bound):
    P(AI) >= THRESH_HIGH      → "AI-Generated",  "HIGH RISK",   "risk-high"
    P(AI) >= THRESH_SUS       → "AI-Generated",  "SUSPICIOUS",  "risk-sus"
    P(AI) >= THRESH_UNCERTAIN → "UNCERTAIN",      "UNCERTAIN",   "risk-uncertain"
    P(AI) <  THRESH_UNCERTAIN → "Human",          "LOW RISK",    "risk-low"
"""

from src.config import THRESH_HIGH, THRESH_SUS, THRESH_UNCERTAIN


def classify(prob_ai: float) -> tuple[str, str, str]:
    """
    Classify an AI-probability score into a verdict, risk band, and CSS class.

    Parameters
    ----------
    prob_ai : float
        P(AI-generated) in [0.0, 1.0] as returned by ``run_inference``.

    Returns
    -------
    verdict : str
        Human-readable verdict label (e.g. ``"AI-Generated"``).
    risk_band : str
        Full risk band description (e.g. ``"HIGH RISK — very likely AI-generated"``).
    risk_css : str
        CSS class name for styling (e.g. ``"risk-high"``).
    """
    if prob_ai >= THRESH_HIGH:
        return "AI-Generated", "HIGH RISK — very likely AI-generated", "risk-high"
    elif prob_ai >= THRESH_SUS:
        return "AI-Generated", "SUSPICIOUS — possibly AI-generated", "risk-sus"
    elif prob_ai >= THRESH_UNCERTAIN:
        return "UNCERTAIN", "UNCERTAIN — manual review advised", "risk-uncertain"
    else:
        return "Human", "LOW RISK — likely human speech", "risk-low"
