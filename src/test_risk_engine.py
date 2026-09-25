"""
test_risk_engine.py — Unit tests for the RiskEngine fusion module.

Covers:
  - Single spikes (must NOT false-trigger Red)
  - Sustained high confidence (must escalate to Red)
  - Amber escalation
  - Reset behaviour
  - Edge cases (empty state, boundary values, mixed sequences)

Run with:
    pytest src/test_risk_engine.py -v
"""

import unittest

from src.risk_engine import RiskEngine, RiskLevel


class TestRiskEngineGreen(unittest.TestCase):
    """Green-state scenarios — low or isolated probabilities."""

    def test_empty_engine_is_green(self) -> None:
        """Before any data is ingested, state should be Green with 0 confidence."""
        engine = RiskEngine(amber_threshold=0.50, red_threshold=0.75)
        state = engine.get_state()
        self.assertEqual(state.level, RiskLevel.GREEN)
        self.assertAlmostEqual(state.confidence, 0.0)
        self.assertEqual(state.window_count, 0)

    def test_low_probabilities_stay_green(self) -> None:
        """All probs below 0.5 should never leave Green."""
        engine = RiskEngine(amber_threshold=0.50, red_threshold=0.75)
        for p in [0.1, 0.2, 0.3, 0.4, 0.49]:
            state = engine.ingest(p)
            self.assertEqual(state.level, RiskLevel.GREEN)

    def test_single_prob_below_threshold_is_green(self) -> None:
        engine = RiskEngine(amber_threshold=0.50, red_threshold=0.75)
        state = engine.ingest(0.45)
        self.assertEqual(state.level, RiskLevel.GREEN)
        self.assertEqual(state.consecutive_amber, 0)


class TestRiskEngineSingleSpike(unittest.TestCase):
    """Single spike tests — must NOT false-trigger Red."""

    def test_single_high_spike_stays_green(self) -> None:
        """One window at 0.95 should NOT trigger Red (needs 3+ consecutive)."""
        engine = RiskEngine(amber_threshold=0.50, red_threshold=0.75)
        state = engine.ingest(0.95)
        self.assertNotEqual(state.level, RiskLevel.RED)
        # Also not Amber (needs 2+ consecutive >= 0.5)
        self.assertEqual(state.level, RiskLevel.GREEN)

    def test_single_spike_after_low_values_stays_green(self) -> None:
        """Low, low, SPIKE, low — should never reach Red."""
        engine = RiskEngine(amber_threshold=0.50, red_threshold=0.75)
        for p in [0.1, 0.2]:
            engine.ingest(p)
        state = engine.ingest(0.90)  # single spike
        self.assertNotEqual(state.level, RiskLevel.RED)
        # Only 1 consecutive >= 0.5 → Green
        self.assertEqual(state.level, RiskLevel.GREEN)
        state = engine.ingest(0.1)   # drops back
        self.assertEqual(state.level, RiskLevel.GREEN)

    def test_spike_sandwich_no_red(self) -> None:
        """High, low, high, low, high — no consecutive run → no Red."""
        engine = RiskEngine(amber_threshold=0.50, red_threshold=0.75)
        for p in [0.80, 0.30, 0.80, 0.30, 0.80]:
            state = engine.ingest(p)
        self.assertNotEqual(state.level, RiskLevel.RED)

    def test_two_high_spikes_separated_by_low(self) -> None:
        """0.9, 0.9, 0.2, 0.9, 0.9 — two runs of 2, never 3 → no Red."""
        engine = RiskEngine(amber_threshold=0.50, red_threshold=0.75)
        for p in [0.9, 0.9]:
            engine.ingest(p)
        engine.ingest(0.2)  # break
        for p in [0.9, 0.9]:
            state = engine.ingest(p)
        self.assertNotEqual(state.level, RiskLevel.RED)
        # Last 2 consecutive >= 0.5 → Amber
        self.assertEqual(state.level, RiskLevel.AMBER)


class TestRiskEngineAmber(unittest.TestCase):
    """Amber escalation — sustained moderate probabilities."""

    def test_two_consecutive_above_050_triggers_amber(self) -> None:
        engine = RiskEngine(amber_threshold=0.50, red_threshold=0.75)
        engine.ingest(0.55)
        state = engine.ingest(0.60)
        self.assertEqual(state.level, RiskLevel.AMBER)

    def test_exactly_050_counts_toward_amber(self) -> None:
        """The amber threshold is inclusive (>= 0.50)."""
        engine = RiskEngine(amber_threshold=0.50, red_threshold=0.75)
        engine.ingest(0.50)
        state = engine.ingest(0.50)
        self.assertEqual(state.level, RiskLevel.AMBER)

    def test_amber_breaks_on_low_value(self) -> None:
        """Amber should drop back to Green when a low value appears."""
        engine = RiskEngine(amber_threshold=0.50, red_threshold=0.75)
        engine.ingest(0.60)
        engine.ingest(0.65)
        self.assertEqual(engine.get_state().level, RiskLevel.AMBER)
        state = engine.ingest(0.30)
        self.assertEqual(state.level, RiskLevel.GREEN)

    def test_three_moderate_values_still_amber(self) -> None:
        """Three values in [0.5, 0.75] should be Amber, not Red."""
        engine = RiskEngine(amber_threshold=0.50, red_threshold=0.75)
        for p in [0.55, 0.60, 0.70]:
            state = engine.ingest(p)
        self.assertEqual(state.level, RiskLevel.AMBER)
        self.assertNotEqual(state.level, RiskLevel.RED)


class TestRiskEngineRed(unittest.TestCase):
    """Red escalation — sustained high probabilities."""

    def test_three_consecutive_above_075_triggers_red(self) -> None:
        engine = RiskEngine(amber_threshold=0.50, red_threshold=0.75)
        engine.ingest(0.80)
        engine.ingest(0.85)
        state = engine.ingest(0.90)
        self.assertEqual(state.level, RiskLevel.RED)

    def test_exactly_above_075_boundary(self) -> None:
        """0.75 is NOT > 0.75, so it should not count toward Red."""
        engine = RiskEngine(amber_threshold=0.50, red_threshold=0.75)
        for _ in range(3):
            state = engine.ingest(0.75)
        # 0.75 is not > 0.75, so Red should not trigger
        self.assertNotEqual(state.level, RiskLevel.RED)
        # But 0.75 >= 0.50, so 3 consecutive → Amber
        self.assertEqual(state.level, RiskLevel.AMBER)

    def test_076_three_times_triggers_red(self) -> None:
        """0.76 IS > 0.75, so three consecutive should trigger Red."""
        engine = RiskEngine(amber_threshold=0.50, red_threshold=0.75)
        for _ in range(3):
            state = engine.ingest(0.76)
        self.assertEqual(state.level, RiskLevel.RED)

    def test_sustained_high_stays_red(self) -> None:
        """Five consecutive high windows should remain Red."""
        engine = RiskEngine(amber_threshold=0.50, red_threshold=0.75)
        for _ in range(5):
            state = engine.ingest(0.90)
        self.assertEqual(state.level, RiskLevel.RED)
        self.assertEqual(state.consecutive_red, 5)

    def test_red_breaks_on_low_value(self) -> None:
        """Red should drop when a low value appears."""
        engine = RiskEngine(amber_threshold=0.50, red_threshold=0.75)
        for _ in range(3):
            engine.ingest(0.85)
        self.assertEqual(engine.get_state().level, RiskLevel.RED)
        state = engine.ingest(0.20)
        self.assertNotEqual(state.level, RiskLevel.RED)
        self.assertEqual(state.level, RiskLevel.GREEN)

    def test_red_takes_priority_over_amber(self) -> None:
        """A run qualifying for both Red and Amber should be Red."""
        engine = RiskEngine(amber_threshold=0.50, red_threshold=0.75)
        for _ in range(4):
            state = engine.ingest(0.90)
        self.assertEqual(state.level, RiskLevel.RED)
        # Also qualifies for Amber (4 consecutive >= 0.5), but Red wins
        self.assertGreaterEqual(state.consecutive_amber, 4)


class TestRiskEngineConfidence(unittest.TestCase):
    """Confidence score correctness."""

    def test_confidence_is_mean_of_history(self) -> None:
        engine = RiskEngine(amber_threshold=0.50, red_threshold=0.75)
        for p in [0.2, 0.4, 0.6, 0.8, 1.0]:
            engine.ingest(p)
        state = engine.get_state()
        expected = (0.2 + 0.4 + 0.6 + 0.8 + 1.0) / 5
        self.assertAlmostEqual(state.confidence, expected, places=4)

    def test_history_limited_to_window_size(self) -> None:
        """Only last 5 values should be in history (default history_size=5)."""
        engine = RiskEngine(amber_threshold=0.50, red_threshold=0.75)
        # Ingest 7 values; only last 5 should count
        for p in [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7]:
            engine.ingest(p)
        state = engine.get_state()
        expected = (0.3 + 0.4 + 0.5 + 0.6 + 0.7) / 5
        self.assertAlmostEqual(state.confidence, expected, places=4)

    def test_confidence_bounded_zero_one(self) -> None:
        engine = RiskEngine(amber_threshold=0.50, red_threshold=0.75)
        engine.ingest(0.0)
        self.assertGreaterEqual(engine.get_state().confidence, 0.0)
        engine.ingest(1.0)
        self.assertLessEqual(engine.get_state().confidence, 1.0)


class TestRiskEngineReset(unittest.TestCase):
    """Reset behaviour — must clear all state cleanly."""

    def test_reset_clears_level_to_green(self) -> None:
        engine = RiskEngine(amber_threshold=0.50, red_threshold=0.75)
        for _ in range(3):
            engine.ingest(0.90)
        self.assertEqual(engine.get_state().level, RiskLevel.RED)
        engine.reset()
        self.assertEqual(engine.get_state().level, RiskLevel.GREEN)

    def test_reset_zeroes_confidence(self) -> None:
        engine = RiskEngine(amber_threshold=0.50, red_threshold=0.75)
        engine.ingest(0.80)
        engine.reset()
        self.assertAlmostEqual(engine.get_state().confidence, 0.0)

    def test_reset_zeroes_window_count(self) -> None:
        engine = RiskEngine(amber_threshold=0.50, red_threshold=0.75)
        for _ in range(5):
            engine.ingest(0.50)
        engine.reset()
        self.assertEqual(engine.get_state().window_count, 0)

    def test_reset_zeroes_consecutive_counters(self) -> None:
        engine = RiskEngine(amber_threshold=0.50, red_threshold=0.75)
        for _ in range(4):
            engine.ingest(0.90)
        engine.reset()
        state = engine.get_state()
        self.assertEqual(state.consecutive_amber, 0)
        self.assertEqual(state.consecutive_red, 0)

    def test_post_reset_can_re_escalate(self) -> None:
        """After reset, a fresh sequence should escalate normally."""
        engine = RiskEngine(amber_threshold=0.50, red_threshold=0.75)
        for _ in range(3):
            engine.ingest(0.90)
        engine.reset()
        # Fresh escalation
        engine.ingest(0.80)
        engine.ingest(0.85)
        state = engine.ingest(0.90)
        self.assertEqual(state.level, RiskLevel.RED)


class TestRiskEngineEdgeCases(unittest.TestCase):
    """Boundary and edge-case tests."""

    def test_clamping_above_one(self) -> None:
        """Values > 1.0 should be clamped to 1.0."""
        engine = RiskEngine(amber_threshold=0.50, red_threshold=0.75)
        state = engine.ingest(1.5)
        self.assertLessEqual(state.confidence, 1.0)

    def test_clamping_below_zero(self) -> None:
        """Values < 0.0 should be clamped to 0.0."""
        engine = RiskEngine(amber_threshold=0.50, red_threshold=0.75)
        state = engine.ingest(-0.5)
        self.assertGreaterEqual(state.confidence, 0.0)

    def test_risk_state_is_frozen(self) -> None:
        """RiskState should be immutable (frozen dataclass)."""
        engine = RiskEngine(amber_threshold=0.50, red_threshold=0.75)
        state = engine.ingest(0.50)
        with self.assertRaises(AttributeError):
            state.level = RiskLevel.RED  # type: ignore[misc]

    def test_window_count_tracks_total(self) -> None:
        engine = RiskEngine(amber_threshold=0.50, red_threshold=0.75)
        for i in range(10):
            engine.ingest(0.5)
        self.assertEqual(engine.get_state().window_count, 10)

    def test_alternating_amber_red_boundary(self) -> None:
        """0.74, 0.76, 0.74, 0.76, 0.76 — alternating around the Red boundary."""
        engine = RiskEngine(amber_threshold=0.50, red_threshold=0.75)
        # 0.74 is >= 0.50 (Amber-eligible) but NOT > 0.75 (Red-ineligible)
        engine.ingest(0.74)  # amber=1, red=0
        engine.ingest(0.76)  # amber=2, red=1
        engine.ingest(0.74)  # amber=3, red=0  (breaks red run)
        engine.ingest(0.76)  # amber=4, red=1
        state = engine.ingest(0.76)  # amber=5, red=2
        self.assertEqual(state.level, RiskLevel.AMBER)
        self.assertNotEqual(state.level, RiskLevel.RED)

    def test_gradual_escalation(self) -> None:
        """Green → Amber → Red progression with gradually increasing values."""
        engine = RiskEngine(amber_threshold=0.50, red_threshold=0.75)
        # Green phase
        state = engine.ingest(0.30)
        self.assertEqual(state.level, RiskLevel.GREEN)
        # Still Green (only 1 window >= 0.5)
        state = engine.ingest(0.55)
        self.assertEqual(state.level, RiskLevel.GREEN)
        # Amber (2 consecutive >= 0.5)
        state = engine.ingest(0.60)
        self.assertEqual(state.level, RiskLevel.AMBER)
        # Amber (3 consecutive >= 0.5, but only 1 > 0.75)
        state = engine.ingest(0.80)
        self.assertEqual(state.level, RiskLevel.AMBER)
        # Amber (4 consecutive >= 0.5, but only 2 > 0.75)
        state = engine.ingest(0.85)
        self.assertEqual(state.level, RiskLevel.AMBER)
        # Red (5 consecutive >= 0.5, 3 consecutive > 0.75)
        state = engine.ingest(0.90)
        self.assertEqual(state.level, RiskLevel.RED)


class TestRiskEngineIntegrationWithStreamPipeline(unittest.TestCase):
    """Smoke test: feed WindowResults from a mock StreamPipeline into RiskEngine."""

    def test_stream_to_engine_flow(self) -> None:
        from unittest.mock import MagicMock
        import numpy as np
        from src.pipeline import StreamPipeline

        ms = MagicMock()
        ms.get_inputs.return_value = [MagicMock(name="input")]
        ms.run.return_value = [np.array([[0.85]], dtype=np.float32)]

        sp = StreamPipeline(session=ms)
        engine = RiskEngine(amber_threshold=0.50, red_threshold=0.75)

        # Generate 6 seconds of audio → at least 3 windows
        t = np.linspace(0, 6.0, int(16_000 * 6.0), endpoint=False)
        pcm = np.sin(2 * np.pi * 440 * t).astype(np.float32)

        results = sp.write(pcm)
        results.extend(sp.flush())

        self.assertGreaterEqual(len(results), 3)

        for r in results:
            state = engine.ingest(r.prob_ai)

        # After 3+ windows at 0.85 → should be Red
        self.assertEqual(state.level, RiskLevel.RED)  # type: ignore[possibly-undefined]


if __name__ == "__main__":
    unittest.main(verbosity=2)
