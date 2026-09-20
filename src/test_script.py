"""
test_script.py -- Quick end-to-end smoke test for the VaniGuard pipeline.

Unlike the formal unittest suites (test_pipeline.py / test_librosa.py), this
script is meant to be run directly from the terminal.  It exercises every
stage of the pipeline using a synthetic sine wave and prints a colour-coded
report so you can verify the whole system is working at a glance.

Usage:
    python test_script.py              # runs all checks
    python test_script.py --verbose    # extra detail on each step
"""

import argparse
import io
import os
import sys
import time
from unittest.mock import MagicMock

import numpy as np
import soundfile as sf
import importlib
import importlib.util

# ── ANSI colours (disabled automatically on Windows without ANSI support) ──
try:
    import colorama
    colorama.init()
    _ANSI = True
except ImportError:
    _ANSI = False

GREEN  = "\033[92m" if _ANSI else ""
RED    = "\033[91m" if _ANSI else ""
YELLOW = "\033[93m" if _ANSI else ""
CYAN   = "\033[96m" if _ANSI else ""
BOLD   = "\033[1m"  if _ANSI else ""
RESET  = "\033[0m"  if _ANSI else ""

PASS = f"{GREEN}[PASS]{RESET}"
FAIL = f"{RED}[FAIL]{RESET}"
INFO = f"{CYAN}[INFO]{RESET}"
WARN = f"{YELLOW}[WARN]{RESET}"


# ── Load app logic (Streamlit mocked) ─────────────────────────────────────
def _load_app():
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


# ── Helpers ───────────────────────────────────────────────────────────────
def _sine(freq=440.0, duration=3.0, sr=16_000):
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    return np.sin(2 * np.pi * freq * t).astype(np.float32)


def _wav_bytes(pcm, sr=16_000):
    buf = io.BytesIO()
    sf.write(buf, pcm, sr, format="WAV", subtype="FLOAT")
    return buf.getvalue()


# ── Check runner ──────────────────────────────────────────────────────────
_results = []


def check(name, fn, verbose=False):
    """Run a single check, record and print result."""
    t0 = time.perf_counter()
    try:
        detail = fn()
        elapsed = (time.perf_counter() - t0) * 1000
        tag = PASS
        status = "ok"
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
        print(f"       {RED}Error: {status}{RESET}")


# ── Individual checks ─────────────────────────────────────────────────────

def run_all(verbose=False):
    app = _load_app()
    SR   = app.SAMPLE_RATE
    DUR  = app.DURATION
    MELS = app.N_MELS
    HOP  = app.HOP_LENGTH
    MIN_DUR = app.MIN_DURATION

    print()
    print(f"{BOLD}{CYAN}VaniGuard — End-to-End Smoke Test{RESET}")
    print("=" * 65)

    # ── Stage 0: imports ──────────────────────────────────────────────
    print(f"\n{BOLD}Stage 0 · Imports & model{RESET}")

    def chk_imports():
        import librosa, onnxruntime, soundfile, pandas, numpy
        return f"librosa {librosa.__version__}  ort {onnxruntime.__version__}"

    check("All required packages importable", chk_imports, verbose)

    def chk_model():
        path = app.MODEL_PATH
        assert os.path.exists(path), f"vaniguard.onnx not found at {path}"
        size_mb = os.path.getsize(path) / 1e6
        return f"{path}  ({size_mb:.1f} MB)"

    check("vaniguard.onnx exists on disk", chk_model, verbose)

    # ── Stage 1: decode ──────────────────────────────────────────────
    print(f"\n{BOLD}Stage 1 · Audio decode (_decode_audio_bytes){RESET}")

    raw_3s = _wav_bytes(_sine(duration=3.0))

    def chk_decode_dtype():
        r = app._decode_audio_bytes(raw_3s, "wav")
        assert r.dtype == np.float32, f"Expected float32, got {r.dtype}"
        return f"dtype={r.dtype}"

    check("Decoded WAV is float32", chk_decode_dtype, verbose)

    def chk_decode_length():
        r = app._decode_audio_bytes(raw_3s, "wav")
        exp = int(SR * 3.0)
        delta = abs(len(r) - exp)
        assert delta < exp * 0.01, f"Length mismatch: {len(r)} vs {exp}"
        return f"samples={len(r)}  expected~{exp}"

    check("Decoded length within 1 % of expected", chk_decode_length, verbose)

    def chk_decode_range():
        r = app._decode_audio_bytes(raw_3s, "wav")
        assert r.max() <= 1.0 + 1e-4 and r.min() >= -1.0 - 1e-4
        return f"min={r.min():.4f}  max={r.max():.4f}"

    check("Decoded values in [-1, 1]", chk_decode_range, verbose)

    def chk_decode_error():
        try:
            app._decode_audio_bytes(b"\x00\xff" * 200, "wav")
            raise AssertionError("Expected RuntimeError — none raised")
        except RuntimeError:
            return "RuntimeError raised correctly"

    check("Garbage bytes raise RuntimeError", chk_decode_error, verbose)

    # ── Stage 2-6: preprocess_audio ───────────────────────────────────
    print(f"\n{BOLD}Stages 2-6 · Preprocessing (preprocess_audio){RESET}")

    def chk_mel_shape():
        mel_norm, mel_tensor, _ = app.preprocess_audio(raw_3s, "wav")
        assert mel_norm.shape[0] == MELS, f"mel_norm rows: {mel_norm.shape[0]}"
        assert mel_tensor.shape == (1, MELS, mel_tensor.shape[2], 1)
        return f"mel_norm={mel_norm.shape}  tensor={mel_tensor.shape}"

    check("Output shapes correct (N_MELS rows, (1,M,T,1) tensor)", chk_mel_shape, verbose)

    def chk_mel_dtype():
        _, mel_tensor, _ = app.preprocess_audio(raw_3s, "wav")
        assert mel_tensor.dtype == np.float32
        return f"dtype={mel_tensor.dtype}"

    check("mel_tensor is float32", chk_mel_dtype, verbose)

    def chk_mel_range():
        mel_norm, mel_tensor, _ = app.preprocess_audio(raw_3s, "wav")
        assert mel_norm.min() >= -1e-6 and mel_norm.max() <= 1.0 + 1e-6
        return f"mel_norm: min={mel_norm.min():.4f}  max={mel_norm.max():.4f}"

    check("mel_norm normalised to [0, 1]", chk_mel_range, verbose)

    def chk_trim():
        _, t5, _ = app.preprocess_audio(_wav_bytes(_sine(duration=5.0)), "wav")
        _, t3, _ = app.preprocess_audio(raw_3s, "wav")
        assert t5.shape[2] == t3.shape[2], "Time steps differ after trim"
        return f"5-s clip trimmed to same T={t5.shape[2]} as 3-s reference"

    check("5-s clip trimmed to same time steps as 3-s reference", chk_trim, verbose)

    def chk_pad():
        _, t1, _ = app.preprocess_audio(_wav_bytes(_sine(duration=1.0)), "wav")
        _, t3, _ = app.preprocess_audio(raw_3s, "wav")
        assert t1.shape[2] == t3.shape[2], "Time steps differ after pad"
        return f"1-s clip padded to same T={t1.shape[2]} as 3-s reference"

    check("1-s clip padded to same time steps as 3-s reference", chk_pad, verbose)

    def chk_reject_short():
        try:
            app.preprocess_audio(_wav_bytes(_sine(duration=0.1)), "wav")
            raise AssertionError("Expected ValueError — none raised")
        except ValueError:
            return "ValueError raised correctly for 0.1-s clip"

    check("Clip < MIN_DURATION raises ValueError", chk_reject_short, verbose)

    def chk_min_dur():
        mel_norm, _, _ = app.preprocess_audio(_wav_bytes(_sine(duration=MIN_DUR)), "wav")
        assert mel_norm is not None
        return f"Clip of exactly {MIN_DUR}s accepted"

    check(f"Clip of exactly MIN_DURATION ({MIN_DUR}s) accepted", chk_min_dur, verbose)

    def chk_deterministic():
        m1, t1, d1 = app.preprocess_audio(raw_3s, "wav")
        m2, t2, d2 = app.preprocess_audio(raw_3s, "wav")
        np.testing.assert_array_equal(m1, m2)
        return "Two runs produced identical output"

    check("Pipeline output is deterministic", chk_deterministic, verbose)

    def chk_silence():
        pcm = np.zeros(int(SR * 3.0), dtype=np.float32)
        m, t, _ = app.preprocess_audio(_wav_bytes(pcm), "wav")
        assert not np.isnan(m).any() and not np.isnan(t).any()
        return "No NaN in mel_norm or mel_tensor for silent input"

    check("Silent input produces no NaN", chk_silence, verbose)

    # ── Stage 7: inference ────────────────────────────────────────────
    print(f"\n{BOLD}Stage 7 · Inference (run_inference){RESET}")

    import math
    T = math.ceil(int(SR * DUR) / HOP) + 1
    dummy_tensor = np.random.rand(1, MELS, T, 1).astype(np.float32)

    def chk_infer_no_model():
        orig = app.session
        try:
            app.session = None
            p = app.run_inference(dummy_tensor)
            assert isinstance(p, float) and 0.0 <= p <= 1.0
            return f"Fallback prob={p:.4f}"
        finally:
            app.session = orig

    check("No-model fallback returns float in [0, 1]", chk_infer_no_model, verbose)

    def chk_infer_mock(ret_val, label):
        def inner():
            ms = MagicMock()
            ms.get_inputs.return_value = [MagicMock(name="input")]
            ms.run.return_value = [np.array([[ret_val]], dtype=np.float32)]
            orig = app.session
            try:
                app.session = ms
                p = app.run_inference(dummy_tensor)
                assert 0.0 <= p <= 1.0, f"Out of range: {p}"
                return f"raw={ret_val}  clamped={p:.4f}"
            finally:
                app.session = orig
        return inner

    check("Mock model output 0.73 forwarded correctly",
          chk_infer_mock(0.73, "0.73"), verbose)
    check("Output > 1.0 clamped to 1.0",
          chk_infer_mock(1.95, ">1"), verbose)
    check("Output < 0.0 clamped to 0.0",
          chk_infer_mock(-0.5, "<0"), verbose)

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
        p = prob  # capture
        def _chk(p=p, v=v_sub, b=b_sub, c=css):
            verd, band, klass = app.classify(p)
            assert v in verd,  f"Expected '{v}' in verdict '{verd}'"
            assert b in band,  f"Expected '{b}' in band '{band}'"
            assert klass == c, f"Expected css '{c}', got '{klass}'"
            return f"verdict='{verd}'  css='{klass}'"
        check(f"classify({prob:.2f}) -> {css}", _chk, verbose)

    # ── Stage 9: history I/O ──────────────────────────────────────────
    print(f"\n{BOLD}Stage 9 · History I/O{RESET}")
    import tempfile, pandas as pd

    tmp = tempfile.NamedTemporaryFile(suffix=".csv", delete=False)
    tmp.close()
    orig_path = app.HISTORY_FILE
    app.HISTORY_FILE = tmp.name
    open(tmp.name, "w").close()

    try:
        def chk_save_load():
            app.save_to_history("smoke.wav", "AI-Generated", 88.0, "HIGH RISK", 0.91)
            df = app.load_history()
            assert len(df) == 1
            assert df.iloc[0]["Filename"] == "smoke.wav"
            return f"Saved and loaded 1 row: Filename='{df.iloc[0]['Filename']}'"

        check("save_to_history + load_history round-trip", chk_save_load, verbose)

        def chk_accumulate():
            for i in range(4):
                app.save_to_history(f"c{i}.wav", "Human", 65.0, "LOW RISK", 0.35)
            df = app.load_history()
            assert len(df) == 5, f"Expected 5 rows, got {len(df)}"
            return f"{len(df)} rows accumulated"

        check("Multiple saves accumulate correctly", chk_accumulate, verbose)

        def chk_clear():
            app.clear_history()
            df = app.load_history()
            assert df.empty
            return "History cleared successfully"

        check("clear_history empties CSV", chk_clear, verbose)

    finally:
        app.HISTORY_FILE = orig_path
        try:
            os.unlink(tmp.name)
        except FileNotFoundError:
            pass

    # ── Stage 10: full end-to-end ─────────────────────────────────────
    print(f"\n{BOLD}Stage 10 · Full end-to-end pipeline{RESET}")

    def chk_e2e_ai():
        mel_norm, mel_tensor, dur = app.preprocess_audio(raw_3s, "wav")
        ms = MagicMock()
        ms.get_inputs.return_value = [MagicMock(name="input")]
        ms.run.return_value = [np.array([[0.92]], dtype=np.float32)]
        orig = app.session
        try:
            app.session = ms
            prob = app.run_inference(mel_tensor)
        finally:
            app.session = orig
        v, b, css = app.classify(prob)
        assert "AI" in v and css == "risk-high"
        return f"prob={prob:.2f}  verdict='{v}'  css='{css}'  dur={dur:.2f}s"

    check("Sine -> preprocess -> mock_infer(0.92) -> AI / HIGH RISK", chk_e2e_ai, verbose)

    def chk_e2e_human():
        _, mel_tensor, _ = app.preprocess_audio(_wav_bytes(_sine(220.0, 2.0)), "wav")
        ms = MagicMock()
        ms.get_inputs.return_value = [MagicMock(name="input")]
        ms.run.return_value = [np.array([[0.08]], dtype=np.float32)]
        orig = app.session
        try:
            app.session = ms
            prob = app.run_inference(mel_tensor)
        finally:
            app.session = orig
        v, b, css = app.classify(prob)
        assert "Human" in v and css == "risk-low"
        return f"prob={prob:.2f}  verdict='{v}'  css='{css}'"

    check("Sine -> preprocess -> mock_infer(0.08) -> Human / LOW RISK", chk_e2e_human, verbose)

    # ── Summary ───────────────────────────────────────────────────────
    print()
    print("=" * 65)
    total  = len(_results)
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
