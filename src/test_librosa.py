"""
test_librosa.py -- Unit tests for librosa feature extraction used in VaniGuard.

Tests cover:
  - melspectrogram output shape, dtype, and value range
  - power_to_db conversion
  - min-max normalisation to [0, 1]
  - resampling with librosa.resample
  - silence handling (no NaN / Inf)
  - frequency content in spectrogram (dominant mel band)
  - consistency between calls

Run with:
    python -m pytest test_librosa.py -v
"""

import unittest

import librosa
import numpy as np

# ── Pipeline constants from config (single source of truth) ───────────────
from src.config import SAMPLE_RATE, N_MELS, N_FFT, HOP_LENGTH, DURATION


# ── Helpers ────────────────────────────────────────────────────────────────

def _sine(freq=440.0, duration=DURATION, sr=SAMPLE_RATE):
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    return np.sin(2 * np.pi * freq * t).astype(np.float32)


def _mel(y, sr=SAMPLE_RATE):
    return librosa.feature.melspectrogram(
        y=y, sr=sr, n_fft=N_FFT, hop_length=HOP_LENGTH, n_mels=N_MELS
    )


def _mel_db(mel):
    return librosa.power_to_db(mel, ref=np.max)


def _norm(mel_db):
    lo, hi = mel_db.min(), mel_db.max()
    return (mel_db - lo) / (hi - lo) if hi > lo else (mel_db - lo)


# ── 1. melspectrogram ──────────────────────────────────────────────────────

class TestMelSpectrogram(unittest.TestCase):

    def test_output_shape_rows(self):
        """melspectrogram must have exactly N_MELS rows."""
        mel = _mel(_sine())
        self.assertEqual(mel.shape[0], N_MELS)

    def test_output_is_2d(self):
        """melspectrogram must be 2-D."""
        self.assertEqual(_mel(_sine()).ndim, 2)

    def test_output_dtype_float32(self):
        """melspectrogram output dtype must be float32."""
        self.assertEqual(_mel(_sine()).dtype, np.float32)

    def test_all_values_non_negative(self):
        """Power spectrogram values must be >= 0."""
        self.assertGreaterEqual(_mel(_sine()).min(), 0.0)

    def test_time_steps_scale_with_duration(self):
        """Longer input should produce more time frames."""
        mel_long  = _mel(_sine(duration=4.0))
        mel_short = _mel(_sine(duration=2.0))
        self.assertGreater(mel_long.shape[1], mel_short.shape[1])

    def test_time_steps_approximately_correct(self):
        """Number of time steps should be close to samples / hop_length."""
        y = _sine(duration=DURATION)
        mel = _mel(y)
        expected_T = int(np.ceil(len(y) / HOP_LENGTH)) + 1
        # Allow 5-frame tolerance for boundary handling
        self.assertAlmostEqual(mel.shape[1], expected_T, delta=5)

    def test_silence_produces_near_zero_spectrogram(self):
        """All-zero input should produce a nearly all-zero power spectrogram."""
        silence = np.zeros(int(SAMPLE_RATE * DURATION), dtype=np.float32)
        mel = _mel(silence)
        self.assertLess(mel.max(), 1e-20)

    def test_louder_signal_larger_spectrogram_values(self):
        """Doubling amplitude should increase spectrogram energy."""
        y = _sine()
        mel_quiet = _mel(y * 0.1)
        mel_loud  = _mel(y * 1.0)
        self.assertGreater(mel_loud.mean(), mel_quiet.mean())

    def test_different_freqs_produce_different_spectra(self):
        """Two different frequencies should yield different spectrogram patterns."""
        mel_440 = _mel(_sine(440.0))
        mel_880 = _mel(_sine(880.0))
        self.assertFalse(np.allclose(mel_440, mel_880))


# ── 2. power_to_db ────────────────────────────────────────────────────────

class TestPowerToDb(unittest.TestCase):

    def test_output_shape_unchanged(self):
        """power_to_db must preserve the spectrogram shape."""
        mel = _mel(_sine())
        db  = _mel_db(mel)
        self.assertEqual(mel.shape, db.shape)

    def test_output_is_non_positive(self):
        """With ref=np.max, power_to_db output must be <= 0 dB."""
        db = _mel_db(_mel(_sine()))
        self.assertLessEqual(db.max(), 0.0 + 1e-6)

    def test_peak_value_is_zero_db(self):
        """The maximum dB value should be exactly 0 (ref=np.max)."""
        db = _mel_db(_mel(_sine()))
        self.assertAlmostEqual(db.max(), 0.0, places=4)

    def test_no_nan_or_inf(self):
        """power_to_db must not produce NaN or Inf for a sine wave."""
        db = _mel_db(_mel(_sine()))
        self.assertFalse(np.isnan(db).any())
        self.assertFalse(np.isinf(db).any())

    def test_dtype_preserved(self):
        """power_to_db should return a float array."""
        db = _mel_db(_mel(_sine()))
        self.assertTrue(np.issubdtype(db.dtype, np.floating))


# ── 3. Min-max normalisation ──────────────────────────────────────────────

class TestNormalisation(unittest.TestCase):

    def test_values_in_zero_to_one(self):
        """Normalised values must lie in [0, 1]."""
        n = _norm(_mel_db(_mel(_sine())))
        self.assertGreaterEqual(n.min(), -1e-6)
        self.assertLessEqual(n.max(), 1.0 + 1e-6)

    def test_max_is_one(self):
        """After normalisation, the maximum value should be 1.0."""
        db = _mel_db(_mel(_sine()))
        if db.max() > db.min():   # non-trivial signal
            n = _norm(db)
            self.assertAlmostEqual(n.max(), 1.0, places=5)

    def test_min_is_zero(self):
        """After normalisation, the minimum value should be 0.0."""
        db = _mel_db(_mel(_sine()))
        if db.max() > db.min():
            n = _norm(db)
            self.assertAlmostEqual(n.min(), 0.0, places=5)

    def test_silence_no_nan(self):
        """Normalisation of silent spectrogram must not produce NaN."""
        silence = np.zeros(int(SAMPLE_RATE * DURATION), dtype=np.float32)
        db = _mel_db(_mel(silence))
        n  = _norm(db)
        self.assertFalse(np.isnan(n).any())

    def test_shape_preserved(self):
        """Normalisation must not change the spectrogram shape."""
        mel = _mel(_sine())
        db  = _mel_db(mel)
        n   = _norm(db)
        self.assertEqual(mel.shape, n.shape)

    def test_deterministic(self):
        """Same input must produce identical normalised output."""
        y = _sine()
        n1 = _norm(_mel_db(_mel(y)))
        n2 = _norm(_mel_db(_mel(y)))
        np.testing.assert_array_equal(n1, n2)


# ── 4. Resampling ─────────────────────────────────────────────────────────

class TestResampling(unittest.TestCase):

    def test_resample_8k_to_16k_doubles_samples(self):
        """Resampling from 8 kHz to 16 kHz should approximately double sample count."""
        y_8k = _sine(sr=8_000, duration=1.0)
        y_16k = librosa.resample(y_8k, orig_sr=8_000, target_sr=16_000)
        self.assertAlmostEqual(len(y_16k), 16_000, delta=100)

    def test_resample_44k_to_16k_reduces_samples(self):
        """Resampling from 44.1 kHz to 16 kHz should reduce sample count."""
        y_44k = _sine(sr=44_100, duration=1.0)
        y_16k = librosa.resample(y_44k, orig_sr=44_100, target_sr=16_000)
        self.assertAlmostEqual(len(y_16k), 16_000, delta=100)

    def test_resample_preserves_dtype(self):
        """Resampled signal should remain float32."""
        y = _sine(sr=44_100, duration=1.0)
        r = librosa.resample(y, orig_sr=44_100, target_sr=SAMPLE_RATE)
        self.assertEqual(r.dtype, np.float32)

    def test_resample_preserves_amplitude(self):
        """Amplitude should not change drastically after resampling (allow 10 % headroom)."""
        y = _sine(sr=44_100, duration=1.0)
        r = librosa.resample(y, orig_sr=44_100, target_sr=SAMPLE_RATE)
        self.assertAlmostEqual(r.max(), 1.0, delta=0.1)

    def test_resample_identity_same_sr(self):
        """Resampling to the same rate should return a nearly identical signal."""
        y = _sine()
        r = librosa.resample(y, orig_sr=SAMPLE_RATE, target_sr=SAMPLE_RATE)
        np.testing.assert_allclose(y, r, rtol=1e-4, atol=1e-4)


# ── 5. Full feature-extraction chain ──────────────────────────────────────

class TestFullFeatureChain(unittest.TestCase):
    """Integration tests that verify the complete feature extraction chain."""

    def _extract(self, freq=440.0, duration=DURATION):
        y = _sine(freq=freq, duration=duration)
        mel = _mel(y)
        db  = _mel_db(mel)
        n   = _norm(db)
        return n

    def test_chain_output_in_zero_to_one(self):
        self.assertGreaterEqual(self._extract().min(), -1e-6)
        self.assertLessEqual(self._extract().max(), 1.0 + 1e-6)

    def test_chain_output_no_nan(self):
        self.assertFalse(np.isnan(self._extract()).any())

    def test_chain_output_no_inf(self):
        self.assertFalse(np.isinf(self._extract()).any())

    def test_chain_shape_consistent(self):
        n1 = self._extract(440.0)
        n2 = self._extract(880.0)
        self.assertEqual(n1.shape, n2.shape)

    def test_chain_deterministic(self):
        n1 = self._extract()
        n2 = self._extract()
        np.testing.assert_array_equal(n1, n2)

    def test_onnx_tensor_reshape(self):
        """Reshaping extracted features to (1, N_MELS, T, 1) must succeed."""
        n = self._extract()
        tensor = n.reshape(1, N_MELS, n.shape[1], 1).astype(np.float32)
        self.assertEqual(tensor.shape[0], 1)
        self.assertEqual(tensor.shape[1], N_MELS)
        self.assertEqual(tensor.shape[3], 1)
        self.assertEqual(tensor.dtype, np.float32)


if __name__ == "__main__":
    unittest.main(verbosity=2)
