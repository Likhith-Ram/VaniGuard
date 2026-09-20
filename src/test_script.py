"""
test_script.py — End-to-end smoke test for the VaniGuard pipeline.

Unlike test_pipeline.py (formal unittest suite), this script is designed
to be run directly from the terminal.  It exercises every pipeline stage
using a synthetic sine wave and prints a colour-coded report.

Usage:
    python src/test_script.py              # runs all checks
    python src/test_script.py --verbose    # extra detail on each step
"""

import argparse
import io
import math
import os
import sys
import time
from unittest.mock import MagicMock

import numpy as np
import soundfile as sf

# ── Direct imports from src package ───────────────────────────────────────
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
    DURATION, HOP_LENGTH, MIN_DURATION, N_MELS, SAMPLE_RATE
)

# ── ANSI colours (disabled automatically on Windows without ANSI support) ──
try:
    import colorama
    colorama.init()
    _ANSI = True
except ImportError:
    _ANSI = False

GREEN = "\033[92m" if _ANSI else ""
RED = "\033[91m" if _ANSI else ""
YELLOW = "\033[93m" if _ANSI else ""
CYAN = "\033[96m" if _ANSI else ""
BOLD = "\033[1m" if _ANSI else ""
RESET = "\033[0m" if _ANSI else ""

PASS = f"{GREEN}[PASS]{RESET}"
FAIL = f"{RED}[FAIL]{RESET}"
INFO = f"{CYAN}[INFO]{RESET}"


# ── Helpers ───────────────────────────────────────────────────────────────
def _sine(freq: float = 440.0, duration: float = 3.0, sr: int = SAMPLE_RATE) -> np.ndarray:
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    return np.sin(2 * np.pi * freq * t).astype(np.float32)


def _wav_bytes(pcm: np.ndarray, sr: int = SAMPLE_RATE) -> bytes:
    buf = io.BytesIO()
    sf.write(buf, pcm, sr, format="WAV", subtype="FLOAT")
    return buf.getvalue()


# ── Check runner ──────────────────────────────────────────────────────────
_results: list[tuple[str, bool, str | None]] = []


def check(name: str, fn, verbose: bool = False) -> None:
    """Run a single check, record and print result."""
    t0 = time.perf_counter()
    try:
        detail = fn()
        elapsed = (time.perf_counter() - t0) * 1000
        tag = PASS
        _results.append((name, True, None))
    except Exception as exc:
        elapsed = (time.perf_counter() - t0) * 1000
        tag = FAIL
        status = str(exc)
        detail = None
        _results.append((name, False, status))

    label = f"{tag} {name:<55} ({elapsed:.1f} ms)"
    print(label)
    if verbose and detail:
        for line in str(detail).splitlines():
            print(f"       {line}")
    if not _results[-1][1]:
        print(f"       {RED}Error: {_results[-1][2]}{RESET}")


# ── Individual checks ─────────────────────────────────────────────────────

def run_all(verbose: bool = False) -> int:
    print()
    print(f"{BOLD}{CYAN}VaniGuard — End-to-End Smoke Test{RESET}")
    print("=" * 65)

    SR = SAMPLE_RATE
    DUR = DURATION
    MELS = N_MELS
    HOP = HOP_LENGTH
    MIN_DUR = MIN_DURATION

    # ── Stage 0: imports ──────────────────────────────────────────────
    print(f"\n{BOLD}Stage 0 · Imports & model{RESET}")

    def chk_imports():
        import librosa
        import onnxruntime
        import soundfile  # noqa: F401
        import pandas  # noqa: F401
        import numpy  # noqa: F401
        return f"librosa {librosa.__version__}  ort {onnxruntime.__version__}"

    check("All required packages importable", chk_imports, verbose)

    from src.config import MODEL_PATH

    def chk_model():
        assert os.path.exists(MODEL_PATH), f"vaniguard.onnx not found at {MODEL_PATH}"
        size_mb = os.path.getsize(MODEL_PATH) / 1e6
        return f"{MODEL_PATH}  ({size_mb:.1f} MB)"

    check("vaniguard.onnx exists on disk", chk_model, verbose)

    # ── Stage 1: decode ──────────────────────────────────────────────
    print(f"\n{BOLD}Stage 1 · Audio decode (_decode_audio_bytes){RESET}")

    raw_3s = _wav_bytes(_sine(duration=3.0))

    def chk_decode_dtype():
        r = _decode_audio_bytes(raw_3s, "wav")
        assert r.dtype == np.float32, f"Expected float32, got {r.dtype}"
        return f"dtype={r.dtype}"

    check("Decoded WAV is float32", chk_decode_dtype, verbose)

    def chk_decode_length():
        r = _decode_audio_bytes(raw_3s, "wav")
        exp = int(SR * 3.0)
        delta = abs(len(r) - exp)
        assert delta < exp * 0.01, f"Length mismatch: {len(r)} vs {exp}"
        return f"samples={len(r)}  expected~{exp}"

    check("Decoded length within 1 % of expected", chk_decode_length, verbose)

    def chk_decode_range():
        r = _decode_audio_bytes(raw_3s, "wav")
        assert r.max() <= 1.0 + 1e-4 and r.min() >= -1.0 - 1e-4
        return f"min={r.min():.4f}  max={r.max():.4f}"

    check("Decoded values in [-1, 1]", chk_decode_range, verbose)

    def chk_decode_error():
        try:
            _decode_audio_bytes(b"\x00\xff" * 200, "wav")
            raise AssertionError("Expected RuntimeError — none raised")
        except RuntimeError:
            return "RuntimeError raised correctly"

    check("Garbage bytes raise RuntimeError", chk_decode_error, verbose)

    # ── Stages 2–6: preprocess_audio ──────────────────────────────────
    print(f"\n{BOLD}Stages 2-6 · Preprocessing (preprocess_audio){RESET}")

    def chk_mel_shape():
        mel_norm, mel_tensor, _ = preprocess_audio(raw_3s, "wav")
        assert mel_norm.shape[0] == MELS, f"mel_norm rows: {mel_norm.shape[0]}"
        assert mel_tensor.shape == (1, MELS, mel_tensor.shape[2], 1)
        return f"mel_norm={mel_norm.shape}  tensor={mel_tensor.shape}"

    check("Output shapes correct (N_MELS rows, (1,M,T,1) tensor)", chk_mel_shape, verbose)

    def chk_mel_dtype():
        _, mel_tensor, _ = preprocess_audio(raw_3s, "wav")
        assert mel_tensor.dtype == np.float32
        return f"dtype={mel_tensor.dtype}"

    check("mel_tensor is float32", chk_mel_dtype, verbose)

    def chk_mel_range():
        mel_norm, _, _ = preprocess_audio(raw_3s, "wav")
        assert mel_norm.min() >= -1e-6 and mel_norm.max() <= 1.0 + 1e-6
        return f"mel_norm: min={mel_norm.min():.4f}  max={mel_norm.max():.4f}"

    check("mel_norm normalised to [0, 1]", chk_mel_range, verbose)

    def chk_trim():
        _, t5, _ = preprocess_audio(_wav_bytes(_sine(duration=5.0)), "wav")
        _, t3, _ = preprocess_audio(raw_3s, "wav")
        assert t5.shape[2] == t3.shape[2], "Time steps differ after trim"
        return f"5-s clip trimmed to same T={t5.shape[2]} as 3-s reference"

    check("5-s clip trimmed to same time steps as 3-s reference", chk_trim, verbose)

    def chk_pad():
        _, t1, _ = preprocess_audio(_wav_bytes(_sine(duration=1.0)), "wav")
        _, t3, _ = preprocess_audio(raw_3s, "wav")
        assert t1.shape[2] == t3.shape[2], "Time steps differ after pad"
        return f"1-s clip padded to same T={t1.shape[2]} as 3-s reference"

    check("1-s clip padded to same time steps as 3-s reference", chk_pad, verbose)

    def chk_reject_short():
        try:
            preprocess_audio(_wav_bytes(_sine(duration=0.1)), "wav")
            raise AssertionError("Expected ValueError — none raised")
        except ValueError:
            return "ValueError raised correctly for 0.1-s clip"

    check("Clip < MIN_DURATION raises ValueError", chk_reject_short, verbose)

    def chk_min_dur():
        mel_norm, _, _ = preprocess_audio(_wav_bytes(_sine(duration=MIN_DUR)), "wav")
        assert mel_norm is not None
        return f"Clip of exactly {MIN_DUR}s accepted"

    check(f"Clip of exactly MIN_DURATION ({MIN_DUR}s) accepted", chk_min_dur, verbose)

    def chk_deterministic():
        m1, t1, d1 = preprocess_audio(raw_3s, "wav")
        m2, t2, d2 = preprocess_audio(raw_3s, "wav")
        np.testing.assert_array_equal(m1, m2)
        return "Two runs produced identical output"

    check("Pipeline output is deterministic", chk_deterministic, verbose)

    def chk_silence():
        pcm = np.zeros(int(SR * 3.0), dtype=np.float32)
        m, t, _ = preprocess_audio(_wav_bytes(pcm), "wav")
        assert not np.isnan(m).any() and not np.isnan(t).any()
        return "No NaN in mel_norm or mel_tensor for silent input"

    check("Silent input produces no NaN", chk_silence, verbose)

    # ── Stage 7: inference ────────────────────────────────────────────
    print(f"\n{BOLD}Stage 7 · Inference (run_inference){RESET}")

    T = math.ceil(int(SR * DUR) / HOP) + 1
    dummy_tensor = np.random.rand(1, MELS, T, 1).astype(np.float32)

    def chk_infer_no_model():
        p = run_inference(None, dummy_tensor)
        assert isinstance(p, float) and 0.0 <= p <= 1.0
        return f"Fallback prob={p:.4f}"

    check("No-model fallback returns float in [0, 1]", chk_infer_no_model, verbose)

    def chk_infer_mock(ret_val: float):
        def inner():
            ms = MagicMock()
            ms.get_inputs.return_value = [MagicMock(name="input")]
            ms.run.return_value = [np.array([[ret_val]], dtype=np.float32)]
            p = run_inference(ms, dummy_tensor)
            assert 0.0 <= p <= 1.0, f"Out of range: {p}"
            return f"raw={ret_val}  clamped={p:.4f}"
        return inner

    check("Mock model output 0.73 forwarded correctly", chk_infer_mock(0.73), verbose)
    check("Output > 1.0 clamped to 1.0",  chk_infer_mock(1.95), verbose)
    check("Output < 0.0 clamped to 0.0",  chk_infer_mock(-0.5), verbose)

    # ── Stage 8: classify ─────────────────────────────────────────────
    print(f"\n{BOLD}Stage 8 · Classification (classify){RESET}")

    cases = [
        (0.99, "AI",        "HIGH RISK",  "risk-high"),
        (0.80, "AI",        "HIGH RISK",  "risk-high"),
        (0.79, "AI",        "SUSPICIOUS", "risk-sus"),
        (0.60, "AI",        "SUSPICIOUS", "risk-sus"),
        (0.59, "UNCERTAIN", "UNCERTAIN",  "risk-uncertain"),
        (0.40, "UNCERTAIN", "UNCERTAIN",  "risk-uncertain"),
        (0.39, "Human",     "LOW RISK",   "risk-low"),
        (0.00, "Human",     "LOW RISK",   "risk-low"),
    ]

    for prob, v_sub, b_sub, css in cases:
        p, v, b, c = prob, v_sub, b_sub, css

        def _chk(p=p, v=v, b=b, c=c):
            verd, band, klass = classify(p)
            assert v in verd,  f"Expected '{v}' in verdict '{verd}'"
            assert b in band,  f"Expected '{b}' in band '{band}'"
            assert klass == c, f"Expected css '{c}', got '{klass}'"
            return f"verdict='{verd}'  css='{klass}'"

        check(f"classify({prob:.2f}) -> {css}", _chk, verbose)

    # ── Stage 9: history I/O ──────────────────────────────────────────
    print(f"\n{BOLD}Stage 9 · History I/O{RESET}")
    import tempfile

    tmp = tempfile.NamedTemporaryFile(suffix=".csv", delete=False)
    tmp.close()
    open(tmp.name, "w").close()

    try:
        def chk_save_load():
            save_to_history("smoke.wav", "AI-Generated", 88.0, "HIGH RISK", 0.91, tmp.name)
            df = load_history(tmp.name)
            assert len(df) == 1
            assert df.iloc[0]["Filename"] == "smoke.wav"
            return "Saved and loaded 1 row"

        check("save_to_history + load_history round-trip", chk_save_load, verbose)

        def chk_accumulate():
            for i in range(4):
                save_to_history(f"c{i}.wav", "Human", 65.0, "LOW RISK", 0.35, tmp.name)
            df = load_history(tmp.name)
            assert len(df) == 5, f"Expected 5 rows, got {len(df)}"
            return f"{len(df)} rows accumulated"

        check("Multiple saves accumulate correctly", chk_accumulate, verbose)

        def chk_clear():
            clear_history(tmp.name)
            df = load_history(tmp.name)
            assert df.empty
            return "History cleared successfully"

        check("clear_history empties CSV", chk_clear, verbose)

    finally:
        try:
            os.unlink(tmp.name)
        except FileNotFoundError:
            pass

    # ── Stage 10: full end-to-end ─────────────────────────────────────
    print(f"\n{BOLD}Stage 10 · Full end-to-end pipeline{RESET}")

    def chk_e2e_ai():
        mel_norm, mel_tensor, dur = preprocess_audio(raw_3s, "wav")
        ms = MagicMock()
        ms.get_inputs.return_value = [MagicMock(name="input")]
        ms.run.return_value = [np.array([[0.92]], dtype=np.float32)]
        prob = run_inference(ms, mel_tensor)
        v, b, css = classify(prob)
        assert "AI" in v and css == "risk-high"
        return f"prob={prob:.2f}  verdict='{v}'  css='{css}'  dur={dur:.2f}s"

    check("Sine -> preprocess -> mock_infer(0.92) -> AI / HIGH RISK", chk_e2e_ai, verbose)

    def chk_e2e_human():
        _, mel_tensor, _ = preprocess_audio(_wav_bytes(_sine(220.0, 2.0)), "wav")
        ms = MagicMock()
        ms.get_inputs.return_value = [MagicMock(name="input")]
        ms.run.return_value = [np.array([[0.08]], dtype=np.float32)]
        prob = run_inference(ms, mel_tensor)
        v, b, css = classify(prob)
        assert "Human" in v and css == "risk-low"
        return f"prob={prob:.2f}  verdict='{v}'  css='{css}'"

    check("Sine -> preprocess -> mock_infer(0.08) -> Human / LOW RISK", chk_e2e_human, verbose)

    # ── Summary ───────────────────────────────────────────────────────
    print()
    print("=" * 65)
    total = len(_results)
    passed = sum(1 for _, ok, _ in _results if ok)
    failed = total - passed

    if failed == 0:
        print(f"{GREEN}{BOLD}All {total} checks passed.{RESET}")
    else:
        print(f"{RED}{BOLD}{failed} of {total} checks FAILED.{RESET}")
        print()
        for name, ok, err in _results:
            if not ok:
                print(f"  {RED}FAIL{RESET} {name}")
                print(f"       {err}")
    print()
    return failed


# ── Entry point ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="VaniGuard smoke test")
    parser.add_argument("--verbose", action="store_true", help="Print step details")
    args = parser.parse_args()

    failed = run_all(verbose=args.verbose)
    sys.exit(failed)
