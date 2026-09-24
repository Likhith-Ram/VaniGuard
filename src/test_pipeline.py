"""
test_pipeline.py — Unit tests for the VaniGuard audio processing pipeline.

Tests cover:
  - _decode_audio_bytes        (Stage 1 — decoding)
  - preprocess_audio           (Stages 1–6 — full pipeline)
  - run_inference              (ONNX inference + fallback)
  - classify                   (verdict + risk-band mapping)
  - load_history / save_to_history / clear_history  (CSV I/O)

Run with:
    pytest src/test_pipeline.py -v
"""

import io
import math
import os
import tempfile
import unittest
from unittest.mock import MagicMock

import numpy as np
import soundfile as sf

# ── Direct imports — no Streamlit mocking needed ──────────────────────────
from src.pipeline import (
    _decode_audio_bytes,
    classify,
    clear_history,
    load_history,
    preprocess_audio,
    run_inference,
    save_to_history,
)
from src.config import (
    DURATION,
    HOP_LENGTH,
    HISTORY_COLS,
    MIN_DURATION,
    N_MELS,
    SAMPLE_RATE,
)


# ── Helpers ────────────────────────────────────────────────────────────────

def _sine_wave(freq: float = 440.0, duration: float = 3.0, sr: int = SAMPLE_RATE) -> np.ndarray:
    """Generate a pure sine wave as float32 PCM."""
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    return np.sin(2 * np.pi * freq * t).astype(np.float32)


def _wav_bytes(pcm: np.ndarray, sr: int = SAMPLE_RATE) -> bytes:
    """Encode float32 numpy array to in-memory WAV bytes."""
    buf = io.BytesIO()
    sf.write(buf, pcm, sr, format="WAV", subtype="FLOAT")
    return buf.getvalue()


# ── 1. _decode_audio_bytes ─────────────────────────────────────────────────

class TestDecodeAudioBytes(unittest.TestCase):

    def test_returns_float32(self) -> None:
        """Decoding a valid WAV must return a float32 array."""
        r = _decode_audio_bytes(_wav_bytes(_sine_wave()), "wav")
        self.assertEqual(r.dtype, np.float32)

    def test_correct_length(self) -> None:
        """Decoded length must be within 1 % of expected sample count."""
        dur = 2.0
        r = _decode_audio_bytes(_wav_bytes(_sine_wave(duration=dur)), "wav")
        exp = int(SAMPLE_RATE * dur)
        self.assertAlmostEqual(len(r), exp, delta=max(1, int(exp * 0.01)))

    def test_values_in_minus_one_to_one(self) -> None:
        """Sine wave samples should stay within [-1, 1]."""
        r = _decode_audio_bytes(_wav_bytes(_sine_wave()), "wav")
        self.assertLessEqual(r.max(), 1.0 + 1e-4)
        self.assertGreaterEqual(r.min(), -1.0 - 1e-4)

    def test_invalid_bytes_raises_runtime_error(self) -> None:
        """Garbage bytes must raise RuntimeError."""
        with self.assertRaises(RuntimeError):
            _decode_audio_bytes(b"\x00\xFF\xAB" * 200, "wav")


# ── 2. preprocess_audio ────────────────────────────────────────────────────

class TestPreprocessAudio(unittest.TestCase):

    def _run(self, duration: float = 3.0, freq: float = 440.0):
        return preprocess_audio(_wav_bytes(_sine_wave(freq=freq, duration=duration)), "wav")

    # Output shapes
    def test_mel_norm_is_2d_with_n_mels_rows(self) -> None:
        mel_norm, _, _ = self._run()
        self.assertEqual(mel_norm.ndim, 2)
        self.assertEqual(mel_norm.shape[0], N_MELS)

    def test_mel_tensor_is_4d_batch_one(self) -> None:
        _, t, _ = self._run()
        self.assertEqual(t.ndim, 4)
        self.assertEqual(t.shape[0], 1)
        self.assertEqual(t.shape[1], N_MELS)
        self.assertEqual(t.shape[3], 1)

    def test_mel_tensor_dtype_float32(self) -> None:
        _, t, _ = self._run()
        self.assertEqual(t.dtype, np.float32)

    # Value ranges
    def test_mel_norm_in_zero_to_one(self) -> None:
        mel_norm, _, _ = self._run()
        self.assertGreaterEqual(mel_norm.min(), -1e-6)
        self.assertLessEqual(mel_norm.max(), 1.0 + 1e-6)

    def test_mel_tensor_in_zero_to_one(self) -> None:
        _, t, _ = self._run()
        self.assertGreaterEqual(t.min(), -1e-6)
        self.assertLessEqual(t.max(), 1.0 + 1e-6)

    # Duration
    def test_duration_returned_for_exact_clip(self) -> None:
        _, _, d = self._run(3.0)
        self.assertAlmostEqual(d, 3.0, delta=0.05)

    def test_duration_returned_for_short_clip(self) -> None:
        _, _, d = self._run(1.5)
        self.assertAlmostEqual(d, 1.5, delta=0.05)

    # Trim / pad
    def test_long_clip_trimmed_to_same_time_steps_as_reference(self) -> None:
        _, long_t, _ = self._run(5.0)
        _, ref_t, _ = self._run(3.0)
        self.assertEqual(long_t.shape[2], ref_t.shape[2])

    def test_short_clip_padded_to_same_time_steps_as_reference(self) -> None:
        _, sh_t, _ = self._run(1.0)
        _, ref_t, _ = self._run(3.0)
        self.assertEqual(sh_t.shape[2], ref_t.shape[2])

    # Rejection
    def test_too_short_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            preprocess_audio(_wav_bytes(_sine_wave(duration=0.1)), "wav")

    def test_exactly_min_duration_accepted(self) -> None:
        mel_norm, _, _ = preprocess_audio(
            _wav_bytes(_sine_wave(duration=MIN_DURATION)), "wav"
        )
        self.assertIsNotNone(mel_norm)

    # Determinism
    def test_pipeline_is_deterministic(self) -> None:
        raw = _wav_bytes(_sine_wave())
        m1, t1, d1 = preprocess_audio(raw, "wav")
        m2, t2, d2 = preprocess_audio(raw, "wav")
        np.testing.assert_array_equal(m1, m2)
        np.testing.assert_array_equal(t1, t2)
        self.assertEqual(d1, d2)

    # Silence
    def test_silent_clip_produces_no_nans(self) -> None:
        pcm = np.zeros(int(SAMPLE_RATE * 3.0), dtype=np.float32)
        m, t, _ = preprocess_audio(_wav_bytes(pcm), "wav")
        self.assertFalse(np.isnan(m).any(), "NaN in mel_norm for silent input")
        self.assertFalse(np.isnan(t).any(), "NaN in mel_tensor for silent input")


# ── 3. run_inference ───────────────────────────────────────────────────────

class TestRunInference(unittest.TestCase):

    def _tensor(self) -> np.ndarray:
        T = math.ceil(int(SAMPLE_RATE * DURATION) / HOP_LENGTH) + 1
        return np.random.rand(1, N_MELS, T, 1).astype(np.float32)

    def test_no_model_returns_float_in_unit_interval(self) -> None:
        """session=None must return a float in [0, 1] (random fallback)."""
        p = run_inference(None, self._tensor())
        self.assertIsInstance(p, float)
        self.assertGreaterEqual(p, 0.0)
        self.assertLessEqual(p, 1.0)

    def test_mock_model_output_forwarded(self) -> None:
        ms = MagicMock()
        ms.get_inputs.return_value = [MagicMock(name="input")]
        ms.run.return_value = [np.array([[0.73]], dtype=np.float32)]
        self.assertAlmostEqual(run_inference(ms, self._tensor()), 0.73, places=4)

    def test_output_clamped_above_one(self) -> None:
        ms = MagicMock()
        ms.get_inputs.return_value = [MagicMock(name="input")]
        ms.run.return_value = [np.array([[1.95]], dtype=np.float32)]
        self.assertLessEqual(run_inference(ms, self._tensor()), 1.0)

    def test_output_clamped_below_zero(self) -> None:
        ms = MagicMock()
        ms.get_inputs.return_value = [MagicMock(name="input")]
        ms.run.return_value = [np.array([[-0.5]], dtype=np.float32)]
        self.assertGreaterEqual(run_inference(ms, self._tensor()), 0.0)

    def test_flat_output_shape_handled(self) -> None:
        ms = MagicMock()
        ms.get_inputs.return_value = [MagicMock(name="input")]
        ms.run.return_value = [np.array([0.55], dtype=np.float32)]
        self.assertAlmostEqual(run_inference(ms, self._tensor()), 0.55, places=4)


# ── 4. classify ────────────────────────────────────────────────────────────

class TestClassify(unittest.TestCase):

    def _chk(self, prob: float, v_sub: str, b_sub: str, css: str) -> None:
        v, b, c = classify(prob)
        self.assertIn(v_sub, v)
        self.assertIn(b_sub, b)
        self.assertEqual(c, css)

    def test_high_risk_at_080(self) -> None:    self._chk(0.80, "AI-Generated", "HIGH RISK",  "risk-high")  # noqa: E501
    def test_high_risk_at_099(self) -> None:    self._chk(0.99, "AI-Generated", "HIGH RISK",  "risk-high")  # noqa: E501
    def test_suspicious_at_060(self) -> None:   self._chk(0.60, "AI-Generated", "SUSPICIOUS", "risk-sus")   # noqa: E501
    def test_suspicious_at_079(self) -> None:   self._chk(0.79, "AI-Generated", "SUSPICIOUS", "risk-sus")   # noqa: E501
    def test_uncertain_at_040(self) -> None:    self._chk(0.40, "UNCERTAIN",    "UNCERTAIN",  "risk-uncertain")  # noqa: E501
    def test_uncertain_at_059(self) -> None:    self._chk(0.59, "UNCERTAIN",    "UNCERTAIN",  "risk-uncertain")  # noqa: E501
    def test_low_risk_at_020(self) -> None:     self._chk(0.20, "Human",        "LOW RISK",   "risk-low")   # noqa: E501
    def test_zero_probability(self) -> None:    self._chk(0.00, "Human",        "LOW RISK",   "risk-low")   # noqa: E501
    def test_one_probability(self) -> None:     self._chk(1.00, "AI-Generated", "HIGH RISK",  "risk-high")  # noqa: E501

    def test_returns_three_values(self) -> None:
        self.assertEqual(len(classify(0.5)), 3)

    def test_all_four_css_classes_reachable(self) -> None:
        css = {classify(p)[2] for p in [0.10, 0.45, 0.65, 0.90]}
        self.assertEqual(css, {"risk-low", "risk-uncertain", "risk-sus", "risk-high"})

    def test_uncertain_verdict_does_not_contain_ai_generated(self) -> None:
        """Regression: 'UNCERTAIN' must NOT match 'AI-Generated' substring."""
        verdict, _, _ = classify(0.50)
        self.assertNotIn(
            "AI-Generated", verdict,
            msg="UNCERTAIN verdict falsely matched 'AI-Generated' — breaks dashboard counts"
        )


# ── 5. History I/O ─────────────────────────────────────────────────────────

class TestHistoryIO(unittest.TestCase):

    def setUp(self) -> None:
        self._tmp = tempfile.NamedTemporaryFile(suffix=".csv", delete=False)
        self._tmp.close()
        open(self._tmp.name, "w").close()  # start blank

    def tearDown(self) -> None:
        try:
            os.unlink(self._tmp.name)
        except FileNotFoundError:
            pass

    def test_empty_file_returns_correct_columns(self) -> None:
        os.unlink(self._tmp.name)
        df = load_history(self._tmp.name)
        self.assertTrue(df.empty)
        for col in HISTORY_COLS:
            self.assertIn(col, df.columns)
        open(self._tmp.name, "w").close()

    def test_save_load_round_trip(self) -> None:
        save_to_history("sample.wav", "🤖 AI-Generated", 87.3, "HIGH RISK", 0.923, self._tmp.name)
        df = load_history(self._tmp.name)
        self.assertEqual(len(df), 1)
        r = df.iloc[0]
        self.assertEqual(r["Filename"], "sample.wav")
        self.assertAlmostEqual(r["Confidence (%)"], 87.3, places=1)
        self.assertAlmostEqual(r["AI Prob"], 0.923, places=3)

    def test_multiple_saves_accumulate(self) -> None:
        for i in range(5):
            save_to_history(f"c{i}.wav", "Human", 65.0, "LOW RISK", 0.35, self._tmp.name)
        self.assertEqual(len(load_history(self._tmp.name)), 5)

    def test_clear_history_empties_csv(self) -> None:
        save_to_history("x.wav", "Human", 65.0, "LOW RISK", 0.35, self._tmp.name)
        clear_history(self._tmp.name)
        df = load_history(self._tmp.name)
        self.assertTrue(df.empty)
        for col in HISTORY_COLS:
            self.assertIn(col, df.columns)

    def test_legacy_csv_missing_ai_prob_backfilled(self) -> None:
        import pandas as pd
        old = pd.DataFrame([{
            "Timestamp": "2025-01-01 00:00:00",
            "Filename": "legacy.wav",
            "Verdict": "Human",
            "Confidence (%)": 70.0,
            "Risk Band": "LOW RISK",
        }])
        old.to_csv(self._tmp.name, index=False)
        df = load_history(self._tmp.name)
        self.assertIn("AI Prob", df.columns)


# ── 6. End-to-end smoke tests ──────────────────────────────────────────────

class TestEndToEnd(unittest.TestCase):

    def test_ai_verdict_high_risk(self) -> None:
        _, mel_tensor, _ = preprocess_audio(_wav_bytes(_sine_wave()), "wav")
        ms = MagicMock()
        ms.get_inputs.return_value = [MagicMock(name="input")]
        ms.run.return_value = [np.array([[0.90]], dtype=np.float32)]
        prob = run_inference(ms, mel_tensor)
        v, _, css = classify(prob)
        self.assertIn("AI-Generated", v)
        self.assertEqual(css, "risk-high")

    def test_human_verdict_low_risk(self) -> None:
        _, mel_tensor, _ = preprocess_audio(_wav_bytes(_sine_wave(220.0, 2.0)), "wav")
        ms = MagicMock()
        ms.get_inputs.return_value = [MagicMock(name="input")]
        ms.run.return_value = [np.array([[0.10]], dtype=np.float32)]
        prob = run_inference(ms, mel_tensor)
        v, _, css = classify(prob)
        self.assertIn("Human", v)
        self.assertEqual(css, "risk-low")


# ── 7. StreamPipeline ─────────────────────────────────────────────────────

from src.pipeline import StreamPipeline, WindowResult  # noqa: E402
from src.config import (  # noqa: E402
    STREAM_WINDOW_SAMPLES,
    STREAM_HOP_SAMPLES,
)


class TestStreamPipeline(unittest.TestCase):
    """Tests for the sliding-window streaming pipeline."""

    def _make_mock_session(self, prob: float = 0.75) -> MagicMock:
        """Return a mock ONNX session that always outputs *prob*."""
        ms = MagicMock()
        ms.get_inputs.return_value = [MagicMock(name="input")]
        ms.run.return_value = [np.array([[prob]], dtype=np.float32)]
        return ms

    # ── Core contract: window count ───────────────────────────────────────

    def test_10s_in_half_second_chunks(self) -> None:
        """
        Feed 10 seconds of audio in 0.5-second chunks.

        Expected windows  = 1 + floor((total_samples - window_samples) / hop_samples)
                          = 1 + floor((160 000 - 64 000) / 16 000)
                          = 1 + 6  =  7
        """
        total_duration = 10.0
        chunk_duration = 0.5
        total_samples = int(SAMPLE_RATE * total_duration)
        chunk_samples = int(SAMPLE_RATE * chunk_duration)

        pcm = _sine_wave(440.0, total_duration)
        ms = self._make_mock_session(0.65)
        sp = StreamPipeline(session=ms)

        all_results: list[WindowResult] = []
        for start in range(0, total_samples, chunk_samples):
            chunk = pcm[start: start + chunk_samples]
            all_results.extend(sp.write(chunk))

        # flush any trailing full window
        all_results.extend(sp.flush())

        expected_windows = 1 + (total_samples - STREAM_WINDOW_SAMPLES) // STREAM_HOP_SAMPLES
        self.assertEqual(
            len(all_results),
            expected_windows,
            f"Expected {expected_windows} windows for {total_duration}s audio, "
            f"got {len(all_results)}",
        )

    def test_window_indices_sequential(self) -> None:
        """Window indices must be 0, 1, 2, …"""
        pcm = _sine_wave(440.0, 10.0)
        sp = StreamPipeline(session=self._make_mock_session())
        results = sp.write(pcm)
        results.extend(sp.flush())
        indices = [r.window_index for r in results]
        self.assertEqual(indices, list(range(len(results))))

    # ── Result fields ─────────────────────────────────────────────────────

    def test_result_fields_populated(self) -> None:
        """Every WindowResult must have valid fields."""
        sp = StreamPipeline(session=self._make_mock_session(0.90))
        results = sp.write(_sine_wave(440.0, 5.0))
        self.assertGreater(len(results), 0)
        r = results[0]
        self.assertIsInstance(r, WindowResult)
        self.assertIsInstance(r.prob_ai, float)
        self.assertIn(r.risk_css, {"risk-high", "risk-sus", "risk-uncertain", "risk-low"})

    def test_mock_prob_forwarded(self) -> None:
        """The mock session probability should flow through to results."""
        sp = StreamPipeline(session=self._make_mock_session(0.42))
        results = sp.write(_sine_wave(440.0, 5.0))
        for r in results:
            self.assertAlmostEqual(r.prob_ai, 0.42, places=4)

    # ── Edge cases ────────────────────────────────────────────────────────

    def test_less_than_one_window_produces_no_results(self) -> None:
        """Feeding < 4 s of audio should produce zero windows."""
        sp = StreamPipeline(session=self._make_mock_session())
        results = sp.write(_sine_wave(440.0, 3.0))
        self.assertEqual(len(results), 0)

    def test_exactly_one_window(self) -> None:
        """Feeding exactly 4 s (= window_samples) should produce one window."""
        sp = StreamPipeline(session=self._make_mock_session())
        results = sp.write(_sine_wave(440.0, 4.0))
        self.assertEqual(len(results), 1)

    def test_reset_clears_state(self) -> None:
        """After reset, buffer and window count are zero."""
        sp = StreamPipeline(session=self._make_mock_session())
        sp.write(_sine_wave(440.0, 5.0))
        sp.reset()
        self.assertEqual(sp.total_windows, 0)
        self.assertEqual(sp.buffered_samples, 0)

    def test_total_windows_property(self) -> None:
        """total_windows must equal sum of all results returned."""
        sp = StreamPipeline(session=self._make_mock_session())
        results = sp.write(_sine_wave(440.0, 8.0))
        results.extend(sp.flush())
        self.assertEqual(sp.total_windows, len(results))

    def test_no_session_runs_fallback(self) -> None:
        """session=None should still work (random fallback)."""
        sp = StreamPipeline(session=None)
        results = sp.write(_sine_wave(440.0, 5.0))
        self.assertGreater(len(results), 0)
        for r in results:
            self.assertGreaterEqual(r.prob_ai, 0.0)
            self.assertLessEqual(r.prob_ai, 1.0)

    def test_multiple_writes_accumulate(self) -> None:
        """Multiple small writes should accumulate in the buffer correctly."""
        sp = StreamPipeline(session=self._make_mock_session())
        # Write 2 s three times = 6 s total → should produce at least 1 window
        all_results: list[WindowResult] = []
        for _ in range(3):
            all_results.extend(sp.write(_sine_wave(440.0, 2.0)))
        total_samples = int(SAMPLE_RATE * 6.0)
        expected = 1 + (total_samples - STREAM_WINDOW_SAMPLES) // STREAM_HOP_SAMPLES
        self.assertEqual(len(all_results), expected)


# ── 8. preprocess_audio_array ──────────────────────────────────────────────

from src.features import preprocess_audio_array  # noqa: E402


class TestPreprocessAudioArray(unittest.TestCase):
    """Tests for the numpy-array-based preprocessing path."""

    def test_output_shapes(self) -> None:
        y = _sine_wave(440.0, 4.0)
        mel_norm, mel_tensor, dur = preprocess_audio_array(y, target_duration=4.0)
        self.assertEqual(mel_norm.ndim, 2)
        self.assertEqual(mel_norm.shape[0], N_MELS)
        self.assertEqual(mel_tensor.ndim, 4)
        self.assertEqual(mel_tensor.shape[0], 1)
        self.assertEqual(mel_tensor.shape[1], N_MELS)
        self.assertEqual(mel_tensor.shape[3], 1)
        self.assertEqual(mel_tensor.dtype, np.float32)

    def test_duration_correct(self) -> None:
        y = _sine_wave(440.0, 2.5)
        _, _, dur = preprocess_audio_array(y, target_duration=4.0)
        self.assertAlmostEqual(dur, 2.5, delta=0.05)

    def test_matches_batch_path_for_3s(self) -> None:
        """Array path with default duration should match batch path (stage 3-6)."""
        y = _sine_wave(440.0, 3.0)
        wav_bytes = _wav_bytes(y)
        m_batch, t_batch, d_batch = preprocess_audio(wav_bytes, "wav")
        m_arr, t_arr, _ = preprocess_audio_array(y, target_duration=3.0)
        np.testing.assert_array_almost_equal(t_batch, t_arr, decimal=4)

    def test_silent_input_no_nans(self) -> None:
        y = np.zeros(int(SAMPLE_RATE * 4.0), dtype=np.float32)
        m, t, _ = preprocess_audio_array(y, target_duration=4.0)
        self.assertFalse(np.isnan(m).any())
        self.assertFalse(np.isnan(t).any())


if __name__ == "__main__":
    unittest.main(verbosity=2)
