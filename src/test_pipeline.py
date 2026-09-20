"""
test_pipeline.py -- Unit tests for the VaniGuard audio processing pipeline.

Tests cover:
  - _decode_audio_bytes        (Stage 1 -- decoding)
  - preprocess_audio           (Stages 1-6 -- full pipeline)
  - run_inference              (ONNX inference)
  - classify                   (verdict + risk-band mapping)
  - load_history / save_to_history / clear_history  (CSV I/O)

Run with:
    python -m pytest test_pipeline.py -v
"""

import io
import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock

import numpy as np
import soundfile as sf
import importlib
import importlib.util


def _load_app_logic():
    """Import app.py with Streamlit fully mocked."""
    st_mock = MagicMock()
    st_mock.cache_resource.return_value = lambda fn: fn
    sys.modules["streamlit"] = st_mock

    spec = importlib.util.spec_from_file_location(
        "app",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.py"),
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


app = _load_app_logic()

SAMPLE_RATE  = app.SAMPLE_RATE
DURATION     = app.DURATION
N_MELS       = app.N_MELS
N_FFT        = app.N_FFT
HOP_LENGTH   = app.HOP_LENGTH
MIN_DURATION = app.MIN_DURATION


# ── Helpers ────────────────────────────────────────────────────────────────

def _sine_wave(freq=440.0, duration=3.0, sr=SAMPLE_RATE):
    """Generate a pure sine wave as float32 PCM."""
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    return np.sin(2 * np.pi * freq * t).astype(np.float32)


def _wav_bytes(pcm, sr=SAMPLE_RATE):
    """Encode float32 numpy array to in-memory WAV bytes."""
    buf = io.BytesIO()
    sf.write(buf, pcm, sr, format="WAV", subtype="FLOAT")
    return buf.getvalue()


# ── 1. _decode_audio_bytes ─────────────────────────────────────────────────

class TestDecodeAudioBytes(unittest.TestCase):

    def test_returns_float32(self):
        """Decoding a valid WAV must return a float32 array."""
        r = app._decode_audio_bytes(_wav_bytes(_sine_wave()), "wav")
        self.assertEqual(r.dtype, np.float32)

    def test_correct_length(self):
        """Decoded length must be within 1 % of expected sample count."""
        dur = 2.0
        r = app._decode_audio_bytes(_wav_bytes(_sine_wave(duration=dur)), "wav")
        exp = int(SAMPLE_RATE * dur)
        self.assertAlmostEqual(len(r), exp, delta=max(1, int(exp * 0.01)))

    def test_values_in_minus_one_to_one(self):
        """Sine wave samples should stay within [-1, 1]."""
        r = app._decode_audio_bytes(_wav_bytes(_sine_wave()), "wav")
        self.assertLessEqual(r.max(), 1.0 + 1e-4)
        self.assertGreaterEqual(r.min(), -1.0 - 1e-4)

    def test_invalid_bytes_raises_runtime_error(self):
        """Garbage bytes must raise RuntimeError."""
        with self.assertRaises(RuntimeError):
            app._decode_audio_bytes(b"\x00\xFF\xAB" * 200, "wav")


# ── 2. preprocess_audio ────────────────────────────────────────────────────

class TestPreprocessAudio(unittest.TestCase):

    def _run(self, duration=3.0, freq=440.0):
        return app.preprocess_audio(_wav_bytes(_sine_wave(freq=freq, duration=duration)), "wav")

    # Output shapes
    def test_mel_norm_is_2d_with_n_mels_rows(self):
        mel_norm, _, _ = self._run()
        self.assertEqual(mel_norm.ndim, 2)
        self.assertEqual(mel_norm.shape[0], N_MELS)

    def test_mel_tensor_is_4d_batch_one(self):
        _, t, _ = self._run()
        self.assertEqual(t.ndim, 4)
        self.assertEqual(t.shape[0], 1)
        self.assertEqual(t.shape[1], N_MELS)
        self.assertEqual(t.shape[3], 1)

    def test_mel_tensor_dtype_float32(self):
        _, t, _ = self._run()
        self.assertEqual(t.dtype, np.float32)

    # Value ranges
    def test_mel_norm_in_zero_to_one(self):
        mel_norm, _, _ = self._run()
        self.assertGreaterEqual(mel_norm.min(), -1e-6)
        self.assertLessEqual(mel_norm.max(), 1.0 + 1e-6)

    def test_mel_tensor_in_zero_to_one(self):
        _, t, _ = self._run()
        self.assertGreaterEqual(t.min(), -1e-6)
        self.assertLessEqual(t.max(), 1.0 + 1e-6)

    # Duration
    def test_duration_returned_for_exact_clip(self):
        _, _, d = self._run(3.0)
        self.assertAlmostEqual(d, 3.0, delta=0.05)

    def test_duration_returned_for_short_clip(self):
        _, _, d = self._run(1.5)
        self.assertAlmostEqual(d, 1.5, delta=0.05)

    # Trim / pad
    def test_long_clip_trimmed_to_same_time_steps_as_reference(self):
        _, long_t, _ = self._run(5.0)
        _, ref_t, _  = self._run(3.0)
        self.assertEqual(long_t.shape[2], ref_t.shape[2])

    def test_short_clip_padded_to_same_time_steps_as_reference(self):
        _, sh_t, _  = self._run(1.0)
        _, ref_t, _ = self._run(3.0)
        self.assertEqual(sh_t.shape[2], ref_t.shape[2])

    # Rejection
    def test_too_short_raises_value_error(self):
        with self.assertRaises(ValueError):
            app.preprocess_audio(_wav_bytes(_sine_wave(duration=0.1)), "wav")

    def test_exactly_min_duration_accepted(self):
        mel_norm, _, _ = app.preprocess_audio(
            _wav_bytes(_sine_wave(duration=MIN_DURATION)), "wav"
        )
        self.assertIsNotNone(mel_norm)

    # Determinism
    def test_pipeline_is_deterministic(self):
        raw = _wav_bytes(_sine_wave())
        m1, t1, d1 = app.preprocess_audio(raw, "wav")
        m2, t2, d2 = app.preprocess_audio(raw, "wav")
        np.testing.assert_array_equal(m1, m2)
        np.testing.assert_array_equal(t1, t2)
        self.assertEqual(d1, d2)

    # Silence
    def test_silent_clip_produces_no_nans(self):
        pcm = np.zeros(int(SAMPLE_RATE * 3.0), dtype=np.float32)
        m, t, _ = app.preprocess_audio(_wav_bytes(pcm), "wav")
        self.assertFalse(np.isnan(m).any(), "NaN in mel_norm for silent input")
        self.assertFalse(np.isnan(t).any(), "NaN in mel_tensor for silent input")


# ── 3. run_inference ───────────────────────────────────────────────────────

class TestRunInference(unittest.TestCase):

    def _tensor(self):
        import math
        T = math.ceil(int(SAMPLE_RATE * DURATION) / HOP_LENGTH) + 1
        return np.random.rand(1, N_MELS, T, 1).astype(np.float32)

    def test_no_model_returns_float_in_unit_interval(self):
        orig = app.session
        try:
            app.session = None
            p = app.run_inference(self._tensor())
            self.assertIsInstance(p, float)
            self.assertGreaterEqual(p, 0.0)
            self.assertLessEqual(p, 1.0)
        finally:
            app.session = orig

    def test_mock_model_output_forwarded(self):
        ms = MagicMock()
        ms.get_inputs.return_value = [MagicMock(name="input")]
        ms.run.return_value = [np.array([[0.73]], dtype=np.float32)]
        orig = app.session
        try:
            app.session = ms
            self.assertAlmostEqual(app.run_inference(self._tensor()), 0.73, places=4)
        finally:
            app.session = orig

    def test_output_clamped_above_one(self):
        ms = MagicMock()
        ms.get_inputs.return_value = [MagicMock(name="input")]
        ms.run.return_value = [np.array([[1.95]], dtype=np.float32)]
        orig = app.session
        try:
            app.session = ms
            self.assertLessEqual(app.run_inference(self._tensor()), 1.0)
        finally:
            app.session = orig

    def test_output_clamped_below_zero(self):
        ms = MagicMock()
        ms.get_inputs.return_value = [MagicMock(name="input")]
        ms.run.return_value = [np.array([[-0.5]], dtype=np.float32)]
        orig = app.session
        try:
            app.session = ms
            self.assertGreaterEqual(app.run_inference(self._tensor()), 0.0)
        finally:
            app.session = orig

    def test_flat_output_shape_handled(self):
        ms = MagicMock()
        ms.get_inputs.return_value = [MagicMock(name="input")]
        ms.run.return_value = [np.array([0.55], dtype=np.float32)]
        orig = app.session
        try:
            app.session = ms
            self.assertAlmostEqual(app.run_inference(self._tensor()), 0.55, places=4)
        finally:
            app.session = orig


# ── 4. classify ────────────────────────────────────────────────────────────

class TestClassify(unittest.TestCase):

    def _chk(self, prob, v_sub, b_sub, css):
        v, b, c = app.classify(prob)
        self.assertIn(v_sub, v)
        self.assertIn(b_sub, b)
        self.assertEqual(c, css)

    def test_high_risk_at_080(self):    self._chk(0.80, "AI-Generated", "HIGH RISK",  "risk-high")
    def test_high_risk_at_099(self):    self._chk(0.99, "AI-Generated", "HIGH RISK",  "risk-high")
    def test_suspicious_at_060(self):   self._chk(0.60, "AI-Generated", "SUSPICIOUS", "risk-sus")
    def test_suspicious_at_079(self):   self._chk(0.79, "AI-Generated", "SUSPICIOUS", "risk-sus")
    def test_uncertain_at_040(self):    self._chk(0.40, "UNCERTAIN",    "UNCERTAIN",  "risk-uncertain")
    def test_uncertain_at_059(self):    self._chk(0.59, "UNCERTAIN",    "UNCERTAIN",  "risk-uncertain")
    def test_low_risk_at_020(self):     self._chk(0.20, "Human",        "LOW RISK",   "risk-low")
    def test_zero_probability(self):    self._chk(0.00, "Human",        "LOW RISK",   "risk-low")
    def test_one_probability(self):     self._chk(1.00, "AI-Generated", "HIGH RISK",  "risk-high")

    def test_returns_three_values(self):
        self.assertEqual(len(app.classify(0.5)), 3)

    def test_all_four_css_classes_reachable(self):
        css = {app.classify(p)[2] for p in [0.10, 0.45, 0.65, 0.90]}
        self.assertEqual(css, {"risk-low", "risk-uncertain", "risk-sus", "risk-high"})

    def test_uncertain_verdict_does_not_contain_ai_generated(self):
        """Regression: 'UNCERTAIN' must NOT match 'AI-Generated' substring check."""
        verdict, _, _ = app.classify(0.50)   # UNCERTAIN zone
        self.assertNotIn("AI-Generated", verdict,
            msg="UNCERTAIN verdict falsely matched 'AI-Generated' — this would break dashboard counts")


# ── 5. History I/O ─────────────────────────────────────────────────────────

class TestHistoryIO(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.NamedTemporaryFile(suffix=".csv", delete=False)
        self._tmp.close()
        self._orig = app.HISTORY_FILE
        app.HISTORY_FILE = self._tmp.name
        open(self._tmp.name, "w").close()   # start blank

    def tearDown(self):
        app.HISTORY_FILE = self._orig
        try:
            os.unlink(self._tmp.name)
        except FileNotFoundError:
            pass

    def test_empty_file_returns_correct_columns(self):
        os.unlink(self._tmp.name)
        df = app.load_history()
        self.assertTrue(df.empty)
        for col in app.HISTORY_COLS:
            self.assertIn(col, df.columns)
        open(self._tmp.name, "w").close()

    def test_save_load_round_trip(self):
        app.save_to_history("sample.wav", "🤖 AI-Generated", 87.3, "HIGH RISK", 0.923)
        df = app.load_history()
        self.assertEqual(len(df), 1)
        r = df.iloc[0]
        self.assertEqual(r["Filename"], "sample.wav")
        self.assertAlmostEqual(r["Confidence (%)"], 87.3, places=1)
        self.assertAlmostEqual(r["AI Prob"], 0.923, places=3)

    def test_multiple_saves_accumulate(self):
        for i in range(5):
            app.save_to_history(f"c{i}.wav", "Human", 65.0, "LOW RISK", 0.35)
        self.assertEqual(len(app.load_history()), 5)

    def test_clear_history_empties_csv(self):
        app.save_to_history("x.wav", "Human", 65.0, "LOW RISK", 0.35)
        app.clear_history()
        df = app.load_history()
        self.assertTrue(df.empty)
        for col in app.HISTORY_COLS:
            self.assertIn(col, df.columns)

    def test_legacy_csv_missing_ai_prob_backfilled(self):
        import pandas as pd
        old = pd.DataFrame([{
            "Timestamp": "2025-01-01 00:00:00",
            "Filename":  "legacy.wav",
            "Verdict":   "Human",
            "Confidence (%)": 70.0,
            "Risk Band": "LOW RISK",
        }])
        old.to_csv(self._tmp.name, index=False)
        df = app.load_history()
        self.assertIn("AI Prob", df.columns)


# ── 6. End-to-end smoke tests ──────────────────────────────────────────────

class TestEndToEnd(unittest.TestCase):

    def _mock_infer(self, mel_tensor, prob_value):
        ms = MagicMock()
        ms.get_inputs.return_value = [MagicMock(name="input")]
        ms.run.return_value = [np.array([[prob_value]], dtype=np.float32)]
        orig = app.session
        try:
            app.session = ms
            return app.run_inference(mel_tensor)
        finally:
            app.session = orig

    def test_ai_verdict_high_risk(self):
        _, mel_tensor, _ = app.preprocess_audio(_wav_bytes(_sine_wave()), "wav")
        prob = self._mock_infer(mel_tensor, 0.90)
        v, _, css = app.classify(prob)
        self.assertIn("AI-Generated", v)
        self.assertEqual(css, "risk-high")

    def test_human_verdict_low_risk(self):
        _, mel_tensor, _ = app.preprocess_audio(_wav_bytes(_sine_wave(220.0, 2.0)), "wav")
        prob = self._mock_infer(mel_tensor, 0.10)
        v, _, css = app.classify(prob)
        self.assertIn("Human", v)
        self.assertEqual(css, "risk-low")


if __name__ == "__main__":
    unittest.main(verbosity=2)
