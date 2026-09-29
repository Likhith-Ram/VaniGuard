# 🎙️ VaniGuard — Deep Audio Cloning Detection

![Python](https://img.shields.io/badge/python-3.10+-blue?logo=python&logoColor=white)
![CI](https://github.com/Likhith-Ram/VaniGuard/actions/workflows/test.yml/badge.svg)
![License](https://img.shields.io/badge/license-MIT-green)
![Coverage](https://img.shields.io/badge/coverage-87.50%25-brightgreen)

> **AI-generated voice detection for Hindi, Tamil, and Telugu.**
> Built with a fine-tuned MobileNetV2 ONNX model, librosa signal processing, and a modern full-stack architecture (FastAPI, Next.js, React Native).

---

## 🚀 Live Demo

**[Try VaniGuard live (Streamlit Demo) →](https://vaniguard-o3g9gcuwexus9ucjquajhc.streamlit.app/)**

## 🏗️ System Architecture

VaniGuard recently migrated from a monolithic Streamlit app to a modular full-stack architecture.

### Data Pipeline (fully in-memory — no temp files, no ffmpeg)

```text
Client (Next.js / Mobile) -> Uploads audio bytes
     │
     ▼
api/main.py      FastAPI Endpoint
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
Client (Next.js / Mobile) receives JSON result & updates UI
```

### Module Map

```text
VaniGuard/
├── api/                 ← FastAPI backend server
├── frontend/            ← Next.js web application
├── mobile/              ← React Native (Expo) mobile application
├── src/                 ← Core AI & Audio Processing module
│   ├── config.py        ← Constants & thresholds
│   ├── audio_io.py      ← Audio decoding
│   ├── features.py      ← Log-Mel Spectrogram preprocessing
│   ├── model.py         ← ONNX inference
│   ├── classify.py      ← Thresholds and logic
│   └── pipeline.py      ← Public re-export façade
├── models/              ← Fine-tuned MobileNetV2 weights (vaniguard.onnx)
├── data/                ← Detection history
└── .github/workflows/   ← CI pipeline configuration
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

---

## 🚀 Local Setup

### Prerequisites
- Python **3.10+**
- Node.js **18+**
- Git

### 1. Python Environment & Core Setup

```bash
git clone https://github.com/Likhith-Ram/VaniGuard.git
cd VaniGuard

# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate
# Activate (macOS/Linux)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Running the FastAPI Backend

```bash
uvicorn api.main:app --reload --port 8000
```
*API will be available at http://localhost:8000*

### 3. Running the Next.js Frontend

In a new terminal:
```bash
cd frontend
npm install
npm run dev
```
*Web app will be available at http://localhost:3000*

### 4. Running the Mobile App (Expo)

In a new terminal:
```bash
cd mobile
npm install
npx expo start
```
*Use the Expo Go app on your phone to scan the QR code.*

### Run Tests

```bash
# Install dev tools
pip install -r requirements-dev.txt

# Unit tests + coverage
pytest src/ -v --cov=src --cov-report=term-missing

# Lint & Type check
flake8 src/
mypy src/
```

---

## ⚠️ Known Limitations

> **Random fallback mode.**
> If `models/vaniguard.onnx` is not found, the app falls back to random predictions. A visible warning banner appears when this occurs.

---

## 📬 Contact

For questions, security disclosures, or collaboration inquiries:
- **General**: [team@vaniguard.ai](mailto:team@vaniguard.ai)
- **Privacy**: [privacy@vaniguard.ai](mailto:privacy@vaniguard.ai)
- **Security**: See [SECURITY.md](SECURITY.md)
- **GitHub Issues**: [github.com/Likhith-Ram/VaniGuard/issues](https://github.com/Likhith-Ram/VaniGuard/issues)
