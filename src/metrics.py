"""
src/metrics.py — EER-based evaluation and threshold calibration.

Replaces hand-tuned thresholds with data-driven ones derived from the
**Equal Error Rate** (EER) operating point.

Key concepts
------------
FAR (False Alarm Rate)
    Fraction of *human* samples incorrectly flagged as AI.
    = FP / (FP + TN)  — this is the source of "real-human false actions".

FRR (False Reject Rate / Miss Rate)
    Fraction of *AI* samples incorrectly passed as human.
    = FN / (FN + TP)

EER
    The threshold where FAR = FRR.  At this point the detector makes
    symmetric errors on both classes — neither humans nor AI samples
    are systematically favoured.

Calibrated thresholds
    Graduated thresholds derived from the FAR/FRR curve:
      THRESH_HIGH      → very low FAR (high precision for "AI" verdict)
      THRESH_SUS       → near the EER point
      THRESH_UNCERTAIN → very low FRR (high recall for AI detection)

Usage::

    from src.metrics import compute_eer, calibrate_thresholds

    eer, eer_thresh = compute_eer(y_true, y_scores)
    thresholds = calibrate_thresholds(y_true, y_scores)
    # thresholds.high, thresholds.suspicious, thresholds.uncertain
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


# ── Data classes ──────────────────────────────────────────────────────────


@dataclass(frozen=True)
class EERResult:
    """
    Result of an EER computation.

    Attributes
    ----------
    eer : float
        Equal Error Rate ∈ [0, 1].  Lower is better.
    threshold : float
        The score threshold at which FAR ≈ FRR.
    """

    eer: float
    threshold: float


@dataclass(frozen=True)
class CalibratedThresholds:
    """
    Graduated classification thresholds derived from FAR/FRR analysis.

    Attributes
    ----------
    high : float
        Threshold for "HIGH RISK" — set where FAR ≤ ``far_target_high``
        (very few humans are falsely flagged).
    suspicious : float
        Threshold for "SUSPICIOUS" — set at the EER operating point.
    uncertain : float
        Threshold for "UNCERTAIN" — set where FRR ≤ ``frr_target_uncertain``
        (very few AI samples are missed).
    eer : float
        The EER value used during calibration.
    """

    high: float
    suspicious: float
    uncertain: float
    eer: float


@dataclass(frozen=True)
class DetectorReport:
    """
    Comprehensive evaluation report for the detector.

    Attributes
    ----------
    eer : float
        Equal Error Rate.
    eer_threshold : float
        Score threshold at EER.
    far_at_eer : float
        FAR at the EER threshold.
    frr_at_eer : float
        FRR at the EER threshold.
    accuracy_at_eer : float
        Classification accuracy at the EER threshold.
    n_positive : int
        Number of AI (positive) samples.
    n_negative : int
        Number of human (negative) samples.
    calibrated : CalibratedThresholds
        Auto-calibrated graduated thresholds.
    """

    eer: float
    eer_threshold: float
    far_at_eer: float
    frr_at_eer: float
    accuracy_at_eer: float
    n_positive: int
    n_negative: int
    calibrated: CalibratedThresholds


# ── Core functions ────────────────────────────────────────────────────────


def compute_far_frr(
    y_true: np.ndarray,
    y_scores: np.ndarray,
    threshold: float,
) -> tuple[float, float]:
    """
    Compute FAR and FRR at a given threshold.

    Parameters
    ----------
    y_true : np.ndarray
        Binary ground-truth labels: 1 = AI-generated, 0 = human.
    y_scores : np.ndarray
        Continuous scores ∈ [0, 1] — P(AI-generated).
    threshold : float
        Classification threshold: score ≥ threshold → predict AI.

    Returns
    -------
    (far, frr) : tuple[float, float]
        FAR and FRR, both ∈ [0, 1].
    """
    y_true = np.asarray(y_true, dtype=np.int32)
    y_scores = np.asarray(y_scores, dtype=np.float64)

    positives = y_true == 1   # AI samples
    negatives = y_true == 0   # human samples

    n_pos = positives.sum()
    n_neg = negatives.sum()

    if n_neg == 0:
        far = 0.0
    else:
        # False alarms: human samples scored >= threshold (falsely called AI)
        fp = ((y_scores[negatives] >= threshold)).sum()
        far = float(fp) / float(n_neg)

    if n_pos == 0:
        frr = 0.0
    else:
        # Misses: AI samples scored < threshold (falsely called human)
        fn = ((y_scores[positives] < threshold)).sum()
        frr = float(fn) / float(n_pos)

    return far, frr


def compute_eer(
    y_true: np.ndarray,
    y_scores: np.ndarray,
    n_thresholds: int = 1000,
) -> EERResult:
    """
    Compute the Equal Error Rate and optimal threshold.

    Sweeps ``n_thresholds`` evenly-spaced thresholds across [0, 1],
    computes FAR and FRR at each, and finds the crossing point via
    linear interpolation.

    Parameters
    ----------
    y_true : np.ndarray
        Binary ground-truth labels: 1 = AI, 0 = human.
    y_scores : np.ndarray
        Continuous scores ∈ [0, 1].
    n_thresholds : int
        Resolution of the threshold sweep.  Default 1000.

    Returns
    -------
    EERResult
        Named tuple with ``.eer`` and ``.threshold``.

    Raises
    ------
    ValueError
        If labels contain fewer than 2 classes.
    """
    y_true = np.asarray(y_true, dtype=np.int32)
    y_scores = np.asarray(y_scores, dtype=np.float64)

    if len(np.unique(y_true)) < 2:
        raise ValueError(
            "y_true must contain both positive (1) and negative (0) samples "
            f"to compute EER. Got unique labels: {np.unique(y_true).tolist()}"
        )

    thresholds = np.linspace(0.0, 1.0, n_thresholds)
    fars = np.empty(n_thresholds)
    frrs = np.empty(n_thresholds)

    for i, t in enumerate(thresholds):
        fars[i], frrs[i] = compute_far_frr(y_true, y_scores, t)

    # Find the crossing point: where FAR - FRR changes sign
    diff = fars - frrs
    # Find the index just before the sign change
    sign_changes = np.where(np.diff(np.sign(diff)))[0]

    if len(sign_changes) == 0:
        # No crossing found — pick the point with smallest |FAR - FRR|
        idx = int(np.argmin(np.abs(diff)))
        eer = float((fars[idx] + frrs[idx]) / 2)
        eer_thresh = float(thresholds[idx])
    else:
        # Linear interpolation between the two bracketing points
        idx = sign_changes[0]
        # Interpolation weight
        d1 = abs(diff[idx])
        d2 = abs(diff[idx + 1])
        denom = d1 + d2
        if denom < 1e-12:
            w = 0.5
        else:
            w = d1 / denom

        eer_thresh = float(thresholds[idx] * (1 - w) + thresholds[idx + 1] * w)
        eer = float(fars[idx] * (1 - w) + fars[idx + 1] * w)

    return EERResult(eer=round(eer, 6), threshold=round(eer_thresh, 6))


def _find_threshold_for_far(
    y_true: np.ndarray,
    y_scores: np.ndarray,
    target_far: float,
    n_thresholds: int = 1000,
) -> float:
    """Find the lowest threshold where FAR ≤ target_far."""
    thresholds = np.linspace(0.0, 1.0, n_thresholds)
    for t in reversed(thresholds):
        far, _ = compute_far_frr(y_true, y_scores, t)
        if far <= target_far:
            return float(t)
    return 1.0  # fallback: reject everything


def _find_threshold_for_frr(
    y_true: np.ndarray,
    y_scores: np.ndarray,
    target_frr: float,
    n_thresholds: int = 1000,
) -> float:
    """Find the highest threshold where FRR ≤ target_frr."""
    thresholds = np.linspace(0.0, 1.0, n_thresholds)
    for t in thresholds:
        _, frr = compute_far_frr(y_true, y_scores, t)
        if frr <= target_frr:
            return float(t)
    return 0.0  # fallback: accept everything


def calibrate_thresholds(
    y_true: np.ndarray,
    y_scores: np.ndarray,
    far_target_high: float = 0.05,
    frr_target_uncertain: float = 0.10,
    n_thresholds: int = 1000,
) -> CalibratedThresholds:
    """
    Derive graduated thresholds from FAR/FRR analysis.

    Parameters
    ----------
    y_true : np.ndarray
        Binary ground-truth labels: 1 = AI, 0 = human.
    y_scores : np.ndarray
        Continuous scores ∈ [0, 1].
    far_target_high : float
        Maximum acceptable FAR for the "HIGH RISK" threshold.
        Default 0.05 (≤ 5 % of humans falsely flagged).
    frr_target_uncertain : float
        Maximum acceptable FRR for the "UNCERTAIN" threshold.
        Default 0.10 (≤ 10 % of AI samples missed).
    n_thresholds : int
        Resolution of the threshold sweep.

    Returns
    -------
    CalibratedThresholds
        Graduated thresholds: ``.high``, ``.suspicious``, ``.uncertain``.
    """
    eer_result = compute_eer(y_true, y_scores, n_thresholds)

    # HIGH: where FAR ≤ far_target_high (very confident "AI" calls)
    thresh_high = _find_threshold_for_far(
        y_true, y_scores, far_target_high, n_thresholds
    )

    # SUSPICIOUS: at the EER operating point
    thresh_sus = eer_result.threshold

    # UNCERTAIN: where FRR ≤ frr_target_uncertain (catch most AI samples)
    thresh_uncertain = _find_threshold_for_frr(
        y_true, y_scores, frr_target_uncertain, n_thresholds
    )

    # Enforce monotonicity: uncertain ≤ suspicious ≤ high
    thresh_sus = max(thresh_sus, thresh_uncertain)
    thresh_high = max(thresh_high, thresh_sus)

    return CalibratedThresholds(
        high=round(thresh_high, 4),
        suspicious=round(thresh_sus, 4),
        uncertain=round(thresh_uncertain, 4),
        eer=eer_result.eer,
    )


def evaluate_detector(
    y_true: np.ndarray,
    y_scores: np.ndarray,
    n_thresholds: int = 1000,
    far_target_high: float = 0.05,
    frr_target_uncertain: float = 0.10,
) -> DetectorReport:
    """
    Full evaluation: EER, FAR/FRR at EER, accuracy, and calibrated thresholds.

    Parameters
    ----------
    y_true : np.ndarray
        Binary ground-truth labels: 1 = AI, 0 = human.
    y_scores : np.ndarray
        Continuous scores ∈ [0, 1].
    n_thresholds : int
        Resolution of the threshold sweep.
    far_target_high : float
        Max FAR for the HIGH RISK threshold.
    frr_target_uncertain : float
        Max FRR for the UNCERTAIN threshold.

    Returns
    -------
    DetectorReport
    """
    y_true = np.asarray(y_true, dtype=np.int32)
    y_scores = np.asarray(y_scores, dtype=np.float64)

    eer_result = compute_eer(y_true, y_scores, n_thresholds)
    far_at_eer, frr_at_eer = compute_far_frr(y_true, y_scores, eer_result.threshold)

    # Accuracy at EER threshold
    preds = (y_scores >= eer_result.threshold).astype(np.int32)
    accuracy = float((preds == y_true).mean())

    calibrated = calibrate_thresholds(
        y_true, y_scores, far_target_high, frr_target_uncertain, n_thresholds
    )

    return DetectorReport(
        eer=eer_result.eer,
        eer_threshold=eer_result.threshold,
        far_at_eer=round(far_at_eer, 6),
        frr_at_eer=round(frr_at_eer, 6),
        accuracy_at_eer=round(accuracy, 6),
        n_positive=int(y_true.sum()),
        n_negative=int((y_true == 0).sum()),
        calibrated=calibrated,
    )
