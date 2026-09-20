# 🎙️ VaniGuard — Deep Audio Cloning Detection

![Python](https://img.shields.io/badge/python-3.10+-blue?logo=python&logoColor=white)
![CI](https://github.com/Likhith-Ram/VaniGuard/actions/workflows/test.yml/badge.svg)
![License](https://img.shields.io/badge/license-MIT-green)
![Coverage](https://img.shields.io/badge/coverage-75.97%25-brightgreen)

> **AI-generated voice detection for Hindi, Tamil, and Telugu.**
> Built with a fine-tuned MobileNetV2 ONNX model, librosa signal processing, and a Streamlit dashboard.

---

## 🚀 Live Demo

> **[https://vaniguard-o3g9gcuwexus9ucjquajhc.streamlit.app/]** 

## 🏗️ System Architecture

### Data Pipeline (fully in-memory — no temp files, no ffmpeg)

```
Browser upload bytes
     │
     ▼
src/audio_io.py  _decode_audio_bytes()
     │   miniaudio (MP3/WAV/FLAC/OGG/M4A) or soundfile fallback
     ▼
numpy float32 PCM array
     │
     ▼
src/features.py  preprocess_audio()
     │   resample → trim/zero-pad → Log-Mel Spectrogram (128 bands)
     │   → power_to_db → min-max norm → reshape (1, 128, T, 1)
     ▼
src/model.py  run_inference(session, mel_tensor)
     │   ONNX InferenceSession (CPUExecutionProvider)
     ▼
P(AI-generated) ∈ [0, 1]
     │
     ▼
src/classify.py  classify(prob_ai)
     │   threshold mapping → verdict + risk band
     ▼
ui/app.py  Streamlit dashboard (verdict banner, metrics, spectrogram)
```

### Module Map

```
VaniGuard/
├── src/
│   ├── config.py        ← All constants & thresholds (single source of truth)
│   ├── audio_io.py      ← Stage 1: decode bytes → float32 PCM
│   ├── features.py      ← Stages 2–6: full preprocessing pipeline
│   ├── model.py         ← ONNX session loading + inference
│   ├── classify.py      ← P(AI) → verdict / risk band / CSS class
│   ├── history.py       ← CSV-based detection history I/O
│   ├── pipeline.py      ← Public re-export façade
│   ├── test_pipeline.py ← Unit tests (pytest)
│   ├── test_librosa.py  ← Librosa feature extraction tests (pytest)
│   └── test_script.py   ← Manual end-to-end smoke test
├── ui/
│   └── app.py           ← Streamlit UI only (~270 lines, zero business logic)
├── models/
│   └── vaniguard.onnx   ← Fine-tuned MobileNetV2 weights
├── data/
│   └── history.csv      ← Detection history (auto-created)
├── notebooks/           ← Training notebooks (add here)
├── requirements.txt
├── requirements-dev.txt
├── run.bat              ← Windows one-click launcher
└── .github/workflows/
    └── test.yml         ← CI: flake8 + mypy + pytest + coverage
```

### Classification Thresholds

| P(AI-generated) | Verdict | Risk Band | CSS Class |
|---|---|---|---|
| ≥ 0.80 | AI-Generated | HIGH RISK | `risk-high` |
| ≥ 0.60 | AI-Generated | SUSPICIOUS | `risk-sus` |
| ≥ 0.40 | UNCERTAIN | UNCERTAIN | `risk-uncertain` |
| < 0.40 | Human | LOW RISK | `risk-low` |

---

## 🤖 Model Details

| Property | Value |
|---|---|
| Architecture | MobileNetV2 (fine-tuned) |
| Format | ONNX (CPU inference) |
| Input | `(1, 128, T, 1)` float32 Log-Mel Spectrogram |
| Output | `float` P(AI-generated) ∈ [0, 1] |
| Training Data | AI4Bharat corpus |
| Languages | Hindi, Tamil, Telugu |
| Accuracy | [FILL IN] |
| F1 Score | [FILL IN] |

---

## 🚀 Local Setup

### Prerequisites
- Python **3.10+**
- Git

### Installation

```bash
# 1. Clone
git clone https://github.com/Likhith-Ram/VaniGuard.git
cd VaniGuard

# 2. Create virtual environment
python -m venv venv

# 3. Activate
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# 4. Install runtime deps
pip install -r requirements.txt
```

### Run the App

```bash
# Option A: direct
streamlit run ui/app.py

# Option B: Windows one-click
run.bat
```

### Run Tests

```bash
# Install dev tools
pip install -r requirements-dev.txt

# Unit tests + coverage
pytest src/test_pipeline.py src/test_librosa.py -v --cov=src --cov-report=term-missing

# Lint
flake8 src/ ui/app.py

# Type check
mypy src/

# Manual smoke test (not pytest)
python src/test_script.py --verbose
```

---

## ⚠️ Known Limitations

> **Single-user local tool only.**
> Concurrent writes to `history.csv` from multiple processes are **not safe** — there is no file locking. If you deploy with multiple simultaneous users, replace the CSV backend with a proper database (SQLite, PostgreSQL, etc.).

> **Random fallback mode.**
> If `models/vaniguard.onnx` is not found, the app falls back to random predictions. A visible warning banner appears on both the sidebar and the Analyze page when this occurs.
