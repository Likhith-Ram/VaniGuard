"""
src/config.py — Single source of truth for all VaniGuard constants.

Import this module everywhere instead of re-declaring magic numbers.
"""

from pathlib import Path

# ── Audio pipeline constants ───────────────────────────────────────────────
SAMPLE_RATE: int = 16_000       # Hz — model was trained at 16 kHz
DURATION: float = 3.0           # seconds — fixed clip length for inference
N_MELS: int = 128               # mel filter banks
N_FFT: int = 1_024              # FFT window size
HOP_LENGTH: int = 512           # frames hop
MIN_DURATION: float = 0.5      # clips shorter than this are rejected (seconds)

# ── Streaming pipeline constants ──────────────────────────────────────────
STREAM_WINDOW_S: float = 4.0    # sliding window length in seconds
STREAM_HOP_S: float = 1.0       # hop between consecutive windows in seconds
STREAM_WINDOW_SAMPLES: int = int(SAMPLE_RATE * STREAM_WINDOW_S)   # 64 000
STREAM_HOP_SAMPLES: int = int(SAMPLE_RATE * STREAM_HOP_S)         # 16 000

# ── Classification thresholds (inclusive lower bound) ─────────────────────
# P(AI) >= THRESH_HIGH      → HIGH RISK
# P(AI) >= THRESH_SUS       → SUSPICIOUS
# P(AI) >= THRESH_UNCERTAIN → UNCERTAIN
# P(AI) <  THRESH_UNCERTAIN → LOW RISK
THRESH_HIGH: float = 0.80
THRESH_SUS: float = 0.60
THRESH_UNCERTAIN: float = 0.40

# ── File paths ─────────────────────────────────────────────────────────────
_ROOT: Path = Path(__file__).resolve().parent.parent  # repo root

MODEL_PATH: str = str(_ROOT / "models" / "vaniguard.onnx")
HISTORY_FILE: str = str(_ROOT / "data" / "history.csv")

# ── History CSV columns ────────────────────────────────────────────────────
HISTORY_COLS: list[str] = [
    "Timestamp",
    "Filename",
    "Verdict",
    "Confidence (%)",
    "Risk Band",
    "AI Prob",
]
