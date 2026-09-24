"""
src/test_metrics.py — Unit tests for EER evaluation and calibration.
"""

import unittest
import numpy as np

from src.metrics import (
    CalibratedThresholds,
    compute_far_frr,
    compute_eer,
    calibrate_thresholds,
    evaluate_detector,
)


class TestMetrics(unittest.TestCase):

    def test_compute_far_frr_perfect_separation(self):
        y_true = np.array([0, 0, 1, 1])
        y_scores = np.array([0.1, 0.2, 0.8, 0.9])

        # Threshold perfectly separating classes
        far, frr = compute_far_frr(y_true, y_scores, 0.5)
        self.assertEqual(far, 0.0)
        self.assertEqual(frr, 0.0)

    def test_compute_far_frr_all_false_alarms(self):
        y_true = np.array([0, 0, 1, 1])
        y_scores = np.array([0.1, 0.2, 0.8, 0.9])

        # Threshold too low -> all negatives called positive
        far, frr = compute_far_frr(y_true, y_scores, 0.0)
        self.assertEqual(far, 1.0)
        self.assertEqual(frr, 0.0)

    def test_compute_far_frr_all_misses(self):
        y_true = np.array([0, 0, 1, 1])
        y_scores = np.array([0.1, 0.2, 0.8, 0.9])

        # Threshold too high -> all positives called negative
        far, frr = compute_far_frr(y_true, y_scores, 1.0)
        self.assertEqual(far, 0.0)
        self.assertEqual(frr, 1.0)

    def test_compute_eer_perfect_separation(self):
        y_true = np.array([0, 0, 1, 1])
        y_scores = np.array([0.1, 0.2, 0.8, 0.9])

        res = compute_eer(y_true, y_scores, n_thresholds=100)
        self.assertEqual(res.eer, 0.0)
        # Threshold could be anything between 0.2 and 0.8, our logic picks crossing point
        self.assertTrue(0.2 < res.threshold <= 0.8)

    def test_compute_eer_overlap(self):
        # 0s: 0.1, 0.6
        # 1s: 0.4, 0.9
        # Overlap at threshold around 0.5 -> 1 false alarm, 1 miss
        y_true = np.array([0, 0, 1, 1])
        y_scores = np.array([0.1, 0.6, 0.4, 0.9])

        res = compute_eer(y_true, y_scores, n_thresholds=1000)
        # 1 error out of 2 samples per class -> 50% error rate
        self.assertAlmostEqual(res.eer, 0.5, places=2)

    def test_compute_eer_single_class_raises_error(self):
        y_true = np.array([1, 1, 1])
        y_scores = np.array([0.8, 0.9, 0.7])
        with self.assertRaises(ValueError):
            compute_eer(y_true, y_scores)

    def test_calibrate_thresholds(self):
        y_true = np.array([0, 0, 0, 0, 1, 1, 1, 1])
        y_scores = np.array([0.1, 0.2, 0.3, 0.4, 0.6, 0.7, 0.8, 0.9])

        # Perfect separation, so high/sus/uncertain might be somewhat similar but ordered correctly
        calibrated = calibrate_thresholds(y_true, y_scores, far_target_high=0.05, frr_target_uncertain=0.1)
        self.assertIsInstance(calibrated, CalibratedThresholds)
        self.assertTrue(calibrated.uncertain <= calibrated.suspicious <= calibrated.high)

    def test_evaluate_detector(self):
        y_true = np.array([0, 0, 1, 1])
        y_scores = np.array([0.1, 0.3, 0.7, 0.9])

        report = evaluate_detector(y_true, y_scores)
        self.assertEqual(report.eer, 0.0)
        self.assertEqual(report.accuracy_at_eer, 1.0)
        self.assertEqual(report.n_positive, 2)
        self.assertEqual(report.n_negative, 2)


class TestClassifyWithEER(unittest.TestCase):

    def test_classify_with_calibrated_thresholds(self):
        from src.classify import classify

        calibrated = CalibratedThresholds(high=0.90, suspicious=0.70, uncertain=0.50, eer=0.1)

        v, rb, css = classify(0.95, calibrated=calibrated)
        self.assertEqual(css, "risk-high")

        v, rb, css = classify(0.75, calibrated=calibrated)
        self.assertEqual(css, "risk-sus")

        v, rb, css = classify(0.55, calibrated=calibrated)
        self.assertEqual(css, "risk-uncertain")

        v, rb, css = classify(0.20, calibrated=calibrated)
        self.assertEqual(css, "risk-low")


if __name__ == "__main__":
    unittest.main()
