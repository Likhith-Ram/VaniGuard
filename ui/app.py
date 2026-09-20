"""
VaniGuard — AI Voice-Clone Detection System
Detects AI-generated voices in Hindi, Tamil, and Telugu audio.

Data Pipeline Architecture
--------------------------
All audio processing is fully in-memory — no temp files, no external binaries.

  Browser upload bytes
       │
       ▼
  miniaudio.decode()          ← native C decoder; handles MP3/WAV/FLAC/OGG/M4A
       │                        without ffmpeg or any system dependency
       ▼
  numpy float32 PCM array
       │
       ▼
  librosa (resample → trim/pad → melspectrogram → power_to_db → min-max norm)
       │
       ▼
  ONNX inference  →  P(AI-generated) ∈ [0, 1]
       │
       ▼
  Verdict + Risk Band
"""

import io
import os
from datetime import datetime

import librosa
import librosa.display
import matplotlib.pyplot as plt
import numpy as np
import onnxruntime as ort
import pandas as pd
import soundfile as sf
import streamlit as st

# miniaudio: self-contained C decoder for MP3/WAV/FLAC/OGG/M4A (no ffmpeg).
# Optional — falls back to soundfile for WAV/FLAC/OGG when unavailable.
try:
    import miniaudio
    _MINIAUDIO_OK = True
except ImportError:
    _MINIAUDIO_OK = False

# ──────────────────────────────────────────────
# CONFIGURATION
# ──────────────────────────────────────────────
SAMPLE_RATE = 16_000
DURATION    = 3.0
N_MELS      = 128
N_FFT       = 1024
HOP_LENGTH  = 512
MIN_DURATION = 0.5          # clips shorter than this are rejected

_BASE_DIR    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_PATH   = os.path.join(_BASE_DIR, "models", "vaniguard.onnx")
HISTORY_FILE = os.path.join(_BASE_DIR, "data", "history.csv")

HISTORY_COLS = ["Timestamp", "Filename", "Verdict", "Confidence (%)", "Risk Band", "AI Prob"]

# ──────────────────────────────────────────────
# PAGE CONFIG  (must be first Streamlit call)
# ──────────────────────────────────────────────
st.set_page_config(
    page_title="Vox Sentinel — AI Voice Detector",
    page_icon="🎙️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ──────────────────────────────────────────────
# CUSTOM CSS — premium dark-glass look
# ──────────────────────────────────────────────
st.markdown("""
<style>
/* Google Font */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

/* Metric cards */
[data-testid="stMetric"] {
    background: linear-gradient(135deg, #1e1b2e 0%, #16132a 100%);
    border: 1px solid #2d2a45;
    border-radius: 14px;
    padding: 1rem 1.2rem;
    box-shadow: 0 4px 24px rgba(124,58,237,.15);
    transition: transform .2s ease, box-shadow .2s ease;
}
[data-testid="stMetric"]:hover {
    transform: translateY(-3px);
    box-shadow: 0 8px 32px rgba(124,58,237,.28);
}
[data-testid="stMetricLabel"] { font-size: .8rem; color: #9ca3af; text-transform: uppercase; letter-spacing: .08em; }
[data-testid="stMetricValue"] { font-size: 2rem; font-weight: 700; color: #e8e8f0; }

/* Verdict banner */
.verdict-ai {
    background: linear-gradient(135deg, #7f1d1d 0%, #450a0a 100%);
    border: 1px solid #ef4444;
    border-radius: 14px;
    padding: 1.4rem 1.6rem;
    text-align: center;
}
.verdict-human {
    background: linear-gradient(135deg, #14532d 0%, #052e16 100%);
    border: 1px solid #22c55e;
    border-radius: 14px;
    padding: 1.4rem 1.6rem;
    text-align: center;
}
.verdict-title { font-size: 1.7rem; font-weight: 700; margin: 0; letter-spacing: .02em; }
.verdict-sub   { font-size: .9rem; color: #d1d5db; margin: .4rem 0 0; }

/* Risk badge */
.risk-badge {
    display: inline-block;
    border-radius: 20px;
    padding: .3rem .9rem;
    font-size: .82rem;
    font-weight: 600;
    letter-spacing: .04em;
}
.risk-high     { background: #7f1d1d; color: #fca5a5; border: 1px solid #ef4444; }
.risk-sus      { background: #431407; color: #fdba74; border: 1px solid #f97316; }
.risk-uncertain{ background: #713f12; color: #fde68a; border: 1px solid #f59e0b; }
.risk-low      { background: #14532d; color: #86efac; border: 1px solid #22c55e; }

/* Sidebar branding */
.sidebar-logo { font-size: 1.6rem; font-weight: 700; letter-spacing: -.02em; }
.sidebar-logo span { color: #7C3AED; }

/* Section divider */
.section-rule { border: none; border-top: 1px solid #2d2a45; margin: 1.4rem 0; }

/* Subtle card wrapper */
.card {
    background: #1a1826;
    border: 1px solid #2d2a45;
    border-radius: 14px;
    padding: 1.2rem 1.4rem;
    margin-bottom: 1rem;
}

/* Pipeline steps */
.pipeline-step {
    display: flex;
    align-items: flex-start;
    gap: .8rem;
    padding: .65rem 0;
    border-bottom: 1px solid #2d2a45;
}
.pipeline-step:last-child { border-bottom: none; }
.step-num {
    min-width: 28px; height: 28px;
    background: #7C3AED; border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-size: .75rem; font-weight: 700; color: #fff;
    flex-shrink: 0; margin-top: .1rem;
}
.step-text { font-size: .9rem; color: #d1d5db; }
.step-text strong { color: #e8e8f0; }
</style>
""", unsafe_allow_html=True)


# ──────────────────────────────────────────────
# MODEL LOADING
# ──────────────────────────────────────────────
@st.cache_resource(show_spinner="Loading VaniGuard model…")
def load_model():
    """Load vaniguard.onnx once per session using CPUExecutionProvider."""
    if not os.path.exists(MODEL_PATH):
        return None, f"Model file not found: {MODEL_PATH}"
    try:
        sess = ort.InferenceSession(MODEL_PATH, providers=["CPUExecutionProvider"])
        _ = sess.get_inputs()[0].name   # validate graph
        return sess, None
    except Exception as exc:
        return None, str(exc)


session, _model_error = load_model()


# ──────────────────────────────────────────────
# AUDIO PROCESSING  (fully in-memory pipeline)
# ──────────────────────────────────────────────

# miniaudio handles all accepted formats (mp3/wav/flac/ogg/m4a) natively;
# no format-map needed — the decoder auto-detects the container.


def _decode_audio_bytes(audio_bytes: bytes, ext: str) -> np.ndarray:
    """
    Stage 1 — Decode raw upload bytes to float32 PCM at SAMPLE_RATE.

    Strategy A (preferred): miniaudio — native C decoder, handles ALL formats
                             including MP3 and M4A, zero external deps.
    Strategy B (fallback):  soundfile + BytesIO — works for WAV/FLAC/OGG only.
                             Used automatically when miniaudio is not installed
                             for the active Python interpreter.
    """
    if _MINIAUDIO_OK:
        # Strategy A — miniaudio path (all formats)
        try:
            decoded = miniaudio.decode(
                audio_bytes,
                output_format=miniaudio.SampleFormat.FLOAT32,
                nchannels=1,
                sample_rate=SAMPLE_RATE,
            )
            return np.frombuffer(decoded.samples, dtype=np.float32).copy()
        except miniaudio.DecodeError as exc:
            raise RuntimeError(
                f"miniaudio could not decode the {ext.upper()} file: {exc}. "
                "Try converting to WAV or FLAC."
            ) from exc
        except Exception as exc:
            raise RuntimeError(f"Decode error: {exc}") from exc
    else:
        # Strategy B — soundfile fallback (WAV / FLAC / OGG only)
        if ext in ("mp3", "m4a"):
            raise RuntimeError(
                f"Cannot decode {ext.upper()} files on this Python installation — "
                "miniaudio is not available. Please upload a WAV or FLAC file instead, "
                "or install miniaudio: `pip install miniaudio`."
            )
        try:
            data, native_sr = sf.read(io.BytesIO(audio_bytes), dtype="float32", always_2d=False)
        except Exception as exc:
            raise RuntimeError(f"soundfile could not decode the {ext.upper()} file: {exc}") from exc
        if data.ndim > 1:
            data = data.mean(axis=1)   # stereo → mono
        if native_sr != SAMPLE_RATE:
            try:
                data = librosa.resample(data, orig_sr=native_sr, target_sr=SAMPLE_RATE)
            except Exception as exc:
                raise RuntimeError(
                    f"Failed to resample {ext.upper()} from {native_sr} Hz to {SAMPLE_RATE} Hz: {exc}"
                ) from exc
        return data


def preprocess_audio(audio_bytes: bytes, ext: str):
    """
    Full in-memory preprocessing pipeline.

    Stage 1  — Decode bytes → float32 PCM via miniaudio  (no filesystem)
    Stage 2  — Validate duration ≥ MIN_DURATION
    Stage 3  — Trim / zero-pad to exactly DURATION seconds
    Stage 4  — Log-Mel Spectrogram  (128 bands, FFT 1024, hop 512)
    Stage 5  — Min-max normalise to [0, 1]
    Stage 6  — Reshape to (1, N_MELS, T, 1) float32 for ONNX

    Returns
    -------
    mel_norm   : np.ndarray  shape (N_MELS, T)          — for display
    mel_tensor : np.ndarray  shape (1, N_MELS, T, 1) float32  — for inference
    duration_s : float       actual clip length before padding

    Raises
    ------
    ValueError   if clip is shorter than MIN_DURATION.
    RuntimeError if decoding fails.
    """
    # Stage 1 — decode
    y = _decode_audio_bytes(audio_bytes, ext)

    # Stage 2 — validate
    duration_s = len(y) / SAMPLE_RATE
    if duration_s < MIN_DURATION:
        raise ValueError(
            f"Audio clip is too short ({duration_s:.2f} s). "
            f"Please upload a clip that is at least {MIN_DURATION} s long."
        )

    # Stage 3 — trim / pad
    target_len = int(SAMPLE_RATE * DURATION)
    if len(y) > target_len:
        y = y[:target_len]
    else:
        y = np.pad(y, (0, target_len - len(y)))

    # Stage 4 — Log-Mel spectrogram
    mel = librosa.feature.melspectrogram(
        y=y, sr=SAMPLE_RATE, n_fft=N_FFT, hop_length=HOP_LENGTH, n_mels=N_MELS
    )
    mel_db = librosa.power_to_db(mel, ref=np.max)

    # Stage 5 — min-max normalise to [0, 1]
    lo, hi = mel_db.min(), mel_db.max()
    mel_norm = (mel_db - lo) / (hi - lo) if hi > lo else (mel_db - lo)

    # Stage 6 — reshape for ONNX
    mel_tensor = mel_norm.reshape(1, N_MELS, mel_norm.shape[1], 1).astype(np.float32)

    return mel_norm, mel_tensor, duration_s


def run_inference(mel_tensor: np.ndarray) -> float:
    """
    Run ONNX inference and return P(AI-generated) in [0, 1].
    Falls back to a random placeholder when the model is unavailable.
    """
    if session is None:
        return float(np.random.uniform(0.0, 1.0))

    input_name = session.get_inputs()[0].name
    output = session.run(None, {input_name: mel_tensor})

    raw = output[0]
    # Handle various output shapes: (1,1), (1,), scalar
    prob = float(raw.flatten()[0])
    return max(0.0, min(1.0, prob))   # clamp to [0,1]


def classify(prob_ai: float):
    """Return (verdict_label, risk_band_label, risk_css_class)."""
    if prob_ai >= 0.80:
        return "AI-Generated", "HIGH RISK — very likely AI-generated", "risk-high"
    elif prob_ai >= 0.60:
        return "AI-Generated", "SUSPICIOUS — possibly AI-generated", "risk-sus"
    elif prob_ai >= 0.40:
        return "UNCERTAIN", "UNCERTAIN — manual review advised", "risk-uncertain"
    else:
        return "Human", "LOW RISK — likely human speech", "risk-low"


# ──────────────────────────────────────────────
# HISTORY I/O
# ──────────────────────────────────────────────
def load_history() -> pd.DataFrame:
    """Load detection history from CSV; return empty frame on any error."""
    if not os.path.exists(HISTORY_FILE):
        return pd.DataFrame(columns=HISTORY_COLS)
    try:
        df = pd.read_csv(HISTORY_FILE)
        
        # Back-compat: rename old 'Confidence' column to 'Confidence (%)'
        if "Confidence" in df.columns and "Confidence (%)" not in df.columns:
            df.rename(columns={"Confidence": "Confidence (%)"}, inplace=True)
            
        # Back-compat: add missing columns introduced in later versions
        for col in HISTORY_COLS:
            if col not in df.columns:
                if col in ["Confidence (%)", "AI Prob"]:
                    df[col] = pd.NA
                else:
                    df[col] = ""
                    
        # Ensure numeric columns are properly typed
        df["Confidence (%)"] = pd.to_numeric(df["Confidence (%)"], errors="coerce")
        df["AI Prob"] = pd.to_numeric(df["AI Prob"], errors="coerce")
        
        return df[HISTORY_COLS]
    except Exception:
        return pd.DataFrame(columns=HISTORY_COLS)


def save_to_history(filename: str, verdict: str, confidence_pct: float, risk_band: str, prob_ai: float):
    """Append a result row to the history CSV."""
    entry = {
        "Timestamp":      datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "Filename":       filename,
        "Verdict":        verdict,
        "Confidence (%)": round(confidence_pct, 1),
        "Risk Band":      risk_band,
        "AI Prob":        round(prob_ai, 4),
    }
    try:
        df = load_history()
        df = pd.concat([df, pd.DataFrame([entry])], ignore_index=True)
        df.to_csv(HISTORY_FILE, index=False)
    except Exception as exc:
        st.warning(f"Could not save to history: {exc}")


def clear_history():
    """Overwrite history CSV with an empty frame."""
    pd.DataFrame(columns=HISTORY_COLS).to_csv(HISTORY_FILE, index=False)


# ──────────────────────────────────────────────
# PAGE — SIDEBAR
# ──────────────────────────────────────────────
def render_sidebar() -> str:
    with st.sidebar:
        st.markdown(
            '<div class="sidebar-logo">🎙️ Vani<span>Guard</span></div>',
            unsafe_allow_html=True,
        )
        st.caption("AI Voice-Clone Detection · Indian Languages")
        st.markdown("<hr class='section-rule'>", unsafe_allow_html=True)

        page = st.radio(
            "Navigation",
            [" Dashboard", " Analyze", " History"],
            label_visibility="collapsed",
        )

        st.markdown("<hr class='section-rule'>", unsafe_allow_html=True)
        st.markdown("#### Model Info")
        st.markdown("**Architecture:** MobileNetV2")
        st.markdown("**Format:** ONNX (CPU)")
        st.markdown("**Languages:** Hindi · Tamil · Telugu")
        st.markdown("**Dataset:** AI4Bharat")

        st.markdown("<hr class='section-rule'>", unsafe_allow_html=True)
        if session is not None:
            st.success("Model ready")
        else:
            st.error("Model unavailable")
            st.caption(f"Reason: {_model_error}")
            st.info("Predictions will be **random** until the model is loaded.")

        # Audio decoder status
        st.markdown("<hr class='section-rule'>", unsafe_allow_html=True)
        if _MINIAUDIO_OK:
            st.success("MP3/WAV/FLAC/OGG supported")
        else:
            st.warning("MP3 not supported — WAV/FLAC/OGG only")
            st.caption(
                "Install miniaudio for MP3 support:\n"
                "`pip install miniaudio`\n"
                "Then restart the app."
            )

    return page


# ──────────────────────────────────────────────
# PAGE — DASHBOARD
# ──────────────────────────────────────────────
def render_dashboard():
    st.markdown("# Dashboard")
    st.markdown(
        "Welcome to **VaniGuard** — a robust AI voice-clone detector tailored for Indian languages."
    )
    st.markdown("<hr class='section-rule'>", unsafe_allow_html=True)

    # ── Metrics ──
    df = load_history()
    total   = len(df)
    # Use "AI-Generated" (not "AI") to avoid false-positive on "UNCERTAIN"
    # which contains the substring "AI" in "UNCERTAI N".
    n_ai    = len(df[df["Verdict"].str.contains("AI-Generated", na=False)]) if total else 0
    n_human = len(df[df["Verdict"].str.contains("Human", na=False)]) if total else 0
    avg_conf = df["Confidence (%)"].mean() if total else 0.0
    ai_rate  = (n_ai / total * 100) if total else 0.0

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Clips Analyzed", total)
    c2.metric("AI Detected",  n_ai)
    c3.metric("Human",       n_human)
    c4.metric("AI Detection Rate", f"{ai_rate:.1f}%")
    c5.metric("Avg Confidence",    f"{avg_conf:.1f}%")

    st.markdown("<hr class='section-rule'>", unsafe_allow_html=True)

    # ── Pipeline explanation ──
    col_left, col_right = st.columns([1, 1], gap="large")

    with col_left:
        st.markdown("### How It Works")
        steps = [
            ("Audio Ingestion",   "File is uploaded and decoded by <b>soundfile / librosa</b>."),
            ("Resampling",        "Audio is resampled to <b>16 kHz</b> mono."),
            ("Trim / Pad",        "Clip is trimmed or zero-padded to exactly <b>3.0 seconds</b>."),
            ("Feature Extraction","A <b>Log-Mel Spectrogram</b> is computed (128 bands, FFT 1024)."),
            ("Normalisation",     "Spectrogram is <b>min-max normalised</b> to [0, 1]."),
            ("Inference",         "<b>MobileNetV2 (ONNX)</b> outputs P(AI-generated) ∈ [0, 1]."),
            ("Classification",    "Probability is mapped to a <b>verdict + risk band</b>."),
        ]
        html = "<div class='card'>"
        for i, (title, desc) in enumerate(steps, 1):
            html += (
                f"<div class='pipeline-step'>"
                f"  <div class='step-num'>{i}</div>"
                f"  <div class='step-text'><strong>{title}</strong><br>{desc}</div>"
                f"</div>"
            )
        html += "</div>"
        st.markdown(html, unsafe_allow_html=True)

    with col_right:
        st.markdown("### Why Indian Languages?")
        st.markdown(
            """<div class='card' style='color:#d1d5db;font-size:.92rem;line-height:1.7'>
            Voice spoofing and deepfakes are a global threat, but models trained primarily on
            Western speech fail to generalise to the unique <strong>phonetics, prosody,</strong>
            and <strong>tonal patterns</strong> of Indian languages.<br><br>
            VaniGuard is trained on <strong>AI4Bharat</strong> corpora, specifically targeting
            <strong>Hindi, Tamil,</strong> and <strong>Telugu</strong> — three of India's most
            widely spoken languages — ensuring culturally relevant and robust detection.<br><br>
            <strong>Risk bands</strong> give operators a nuanced signal beyond a binary verdict,
            enabling graduated response policies.
            </div>""",
            unsafe_allow_html=True,
        )

        st.markdown("### Risk Bands")
        bands = [
            ("HIGH RISK",  "risk-high",      "P(AI) ≥ 0.80 — very likely synthetic"),
            ("SUSPICIOUS", "risk-sus",        "P(AI) ≥ 0.60 — possibly synthetic"),
            ("UNCERTAIN",  "risk-uncertain",  "P(AI) ∈ [0.40, 0.60) — review advised"),
            ("LOW RISK",   "risk-low",        "P(AI) < 0.40 — likely human"),
        ]
        for label, css, desc in bands:
            st.markdown(
                f"<div style='margin:.35rem 0'>"
                f"<span class='risk-badge {css}'>{label}</span> "
                f"<span style='font-size:.85rem;color:#9ca3af'>{desc}</span>"
                f"</div>",
                unsafe_allow_html=True,
            )


# ──────────────────────────────────────────────
# PAGE — ANALYZE
# ──────────────────────────────────────────────
def render_analyze():
    st.markdown("# Analyze Audio")
    st.markdown(
        "Upload an audio clip to determine whether the voice is **human** or **AI-generated**."
    )
    st.markdown("<hr class='section-rule'>", unsafe_allow_html=True)

    uploaded = st.file_uploader(
        "Choose an audio file",
        type=["wav", "mp3", "ogg", "flac", "m4a"],
        help="Supported: WAV, MP3, OGG, FLAC, M4A · Max 50 MB",
    )

    if uploaded is None:
        st.info("Upload an audio file above to get started.")
        return

    # Audio player
    ext = uploaded.name.rsplit(".", 1)[-1].lower()
    st.audio(uploaded, format=f"audio/{ext}")

    st.markdown(f"**File:** `{uploaded.name}` &nbsp;·&nbsp; **Size:** {uploaded.size / 1024:.1f} KB")

    if not st.button("Run Detection", type="primary", use_container_width=False):
        return

    # ── Fully in-memory pipeline — no temp files, no ffmpeg ──────────────
    # audio_bytes are the raw upload bytes; passed directly to miniaudio.
    audio_bytes = uploaded.getvalue()
    try:
        with st.spinner("Analysing audio…"):
            mel_norm, mel_tensor, duration_s = preprocess_audio(audio_bytes, ext)
            prob_ai = run_inference(mel_tensor)

    except (ValueError, RuntimeError) as exc:
        st.error(f"{exc}")
        return
    except Exception as exc:
        st.error(f"Unexpected error processing audio: {exc}")
        return

    # ── Classification ────────────────────────────────────────────────────
    verdict, risk_band, risk_css = classify(prob_ai)
    # "AI-Generated" check avoids false-positive: "UNCERTAIN" contains "AI"
    is_ai = "AI-Generated" in verdict
    confidence = prob_ai if is_ai else (1.0 - prob_ai)
    confidence_pct = confidence * 100

    # ── Verdict banner ────────────────────────────────────────────────────
    if is_ai:
        st.markdown(
            f"<div class='verdict-ai'>"
            f"<p class='verdict-title'>AI-Generated Voice Detected</p>"
            f"<p class='verdict-sub'>This clip has characteristics consistent with synthetic speech.</p>"
            f"</div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f"<div class='verdict-human'>"
            f"<p class='verdict-title'>Human Voice Verified</p>"
            f"<p class='verdict-sub'>This clip appears to be authentic human speech.</p>"
            f"</div>",
            unsafe_allow_html=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Metrics row ───────────────────────────────────────────────────────
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Verdict",         verdict)
    m2.metric("AI Probability",  f"{prob_ai * 100:.1f}%")
    m3.metric("Confidence",      f"{confidence_pct:.1f}%")
    m4.metric("Duration",        f"{duration_s:.2f} s")

    # Risk badge
    st.markdown(
        f"<div style='margin:.6rem 0'>"
        f"<span class='risk-badge {risk_css}'>{risk_band}</span>"
        f"</div>",
        unsafe_allow_html=True,
    )

    # Confidence progress bar
    st.progress(float(confidence), text=f"Confidence: {confidence_pct:.1f}%")

    # ── Mel Spectrogram (collapsible) ─────────────────────────────────────
    with st.expander("View Mel Spectrogram", expanded=False):
        fig, ax = plt.subplots(figsize=(10, 3))
        fig.patch.set_facecolor("#1a1826")
        ax.set_facecolor("#1a1826")
        img = librosa.display.specshow(
            mel_norm, sr=SAMPLE_RATE, hop_length=HOP_LENGTH,
            x_axis="time", y_axis="mel", ax=ax, cmap="magma"
        )
        fig.colorbar(img, ax=ax, format="%+2.f dB")
        ax.set_title("Log-Mel Spectrogram", color="#e8e8f0", fontsize=11)
        ax.tick_params(colors="#9ca3af")
        for spine in ax.spines.values():
            spine.set_edgecolor("#2d2a45")
        plt.tight_layout()
        st.pyplot(fig)
        plt.close(fig)

    # ── Save result ───────────────────────────────────────────────────────
    save_to_history(uploaded.name, verdict, confidence_pct, risk_band, prob_ai)
    st.caption("Result saved to history.")


# ──────────────────────────────────────────────
# PAGE — HISTORY
# ──────────────────────────────────────────────
def render_history():
    st.markdown("# Detection History")
    st.markdown("<hr class='section-rule'>", unsafe_allow_html=True)

    df = load_history()

    if df.empty:
        st.info("No history yet. Analyze some audio files first.")
        return

    # Newest first
    df_display = df.iloc[::-1].reset_index(drop=True)

    # Summary metrics
    total   = len(df)
    # Use "AI-Generated" (not "AI") to avoid false-positive on "UNCERTAIN"
    n_ai    = df["Verdict"].str.contains("AI-Generated", na=False).sum()
    n_human = df["Verdict"].str.contains("Human", na=False).sum()

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Analyzed", total)
    c2.metric("AI Detected",    int(n_ai))
    c3.metric("Human",          int(n_human))

    st.markdown("<br>", unsafe_allow_html=True)

    # Styled dataframe
    def style_verdict(val):
        if "AI" in str(val):
            return "color: #fca5a5; font-weight: 600"
        if "Human" in str(val):
            return "color: #86efac; font-weight: 600"
        return "color: #fde68a"

    styled = df_display.style.map(style_verdict, subset=["Verdict"])
    st.dataframe(styled, use_container_width=True, height=400)

    # Action buttons
    col_dl, col_clr, _ = st.columns([1, 1, 4])
    with col_dl:
        csv_bytes = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "Download CSV",
            data=csv_bytes,
            file_name="vaniguard_history.csv",
            mime="text/csv",
            use_container_width=True,
        )
    with col_clr:
        if st.button("Clear History", use_container_width=True):
            clear_history()
            st.success("History cleared.")
            st.rerun()


# ──────────────────────────────────────────────
# ENTRY POINT
# ──────────────────────────────────────────────
def main():
    page = render_sidebar()

    if "Dashboard" in page:
        render_dashboard()
    elif "Analyze" in page:
        render_analyze()
    elif "History" in page:
        render_history()


if __name__ == "__main__":
    main()
