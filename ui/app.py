"""
ui/app.py — VaniGuard Streamlit UI

All business logic lives in src/. This file contains only:
  - Page config & CSS
  - Model loading (wrapped with @st.cache_resource — a Streamlit concern)
  - render_sidebar / render_dashboard / render_analyze / render_history / main()

Data pipeline (no Streamlit imports):
  Browser upload bytes
       │
       ▼
  src.audio_io._decode_audio_bytes()    ← miniaudio / soundfile
       │
       ▼
  src.features.preprocess_audio()       ← resample → trim/pad → mel → norm → tensor
       │
       ▼
  src.model.run_inference()             ← ONNX  P(AI-generated) ∈ [0, 1]
       │
       ▼
  src.classify.classify()               ← verdict + risk band
"""

import os
import sys

import librosa
import librosa.display
import matplotlib.pyplot as plt
import streamlit as st

# ── make repo root importable when launched via `streamlit run ui/app.py` ──
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from src.classify import classify                                      # noqa: E402
from src.config import HOP_LENGTH, SAMPLE_RATE                        # noqa: E402
from src.features import preprocess_audio                              # noqa: E402
from src.history import clear_history, load_history, save_to_history  # noqa: E402
from src.model import load_model, run_inference                        # noqa: E402
from src.audio_io import _MINIAUDIO_OK                                # noqa: E402

# ── max upload size (must match .streamlit/config.toml) ───────────────────
_MAX_UPLOAD_MB = 50

# ──────────────────────────────────────────────
# PAGE CONFIG  (must be first Streamlit call)
# ──────────────────────────────────────────────
st.set_page_config(
    page_title="VaniGuard — AI Voice Detector",
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
[data-testid="stMetricLabel"] { font-size: .8rem; color: #9ca3af; text-transform: uppercase; letter-spacing: .08em; }  # noqa: E501
[data-testid="stMetricValue"] { font-size: 2rem; font-weight: 700; color: #e8e8f0; }

/* Verdict banner */
.verdict-ai {
    background: linear-gradient(135deg, #7f1d1d 0%, #450a0a 100%);
    border: 1px solid #ef4444; border-radius: 14px;
    padding: 1.4rem 1.6rem; text-align: center;
}
.verdict-human {
    background: linear-gradient(135deg, #14532d 0%, #052e16 100%);
    border: 1px solid #22c55e; border-radius: 14px;
    padding: 1.4rem 1.6rem; text-align: center;
}
.verdict-title { font-size: 1.7rem; font-weight: 700; margin: 0; letter-spacing: .02em; }
.verdict-sub   { font-size: .9rem; color: #d1d5db; margin: .4rem 0 0; }

/* Risk badge */
.risk-badge { display: inline-block; border-radius: 20px; padding: .3rem .9rem;
              font-size: .82rem; font-weight: 600; letter-spacing: .04em; }
.risk-high     { background: #7f1d1d; color: #fca5a5; border: 1px solid #ef4444; }
.risk-sus      { background: #431407; color: #fdba74; border: 1px solid #f97316; }
.risk-uncertain{ background: #713f12; color: #fde68a; border: 1px solid #f59e0b; }
.risk-low      { background: #14532d; color: #86efac; border: 1px solid #22c55e; }

/* Sidebar branding */
.sidebar-logo { font-size: 1.6rem; font-weight: 700; letter-spacing: -.02em; }
.sidebar-logo span { color: #7C3AED; }

/* Section divider */
.section-rule { border: none; border-top: 1px solid #2d2a45; margin: 1.4rem 0; }

/* Card wrapper */
.card { background: #1a1826; border: 1px solid #2d2a45; border-radius: 14px;
        padding: 1.2rem 1.4rem; margin-bottom: 1rem; }

/* Pipeline steps */
.pipeline-step { display: flex; align-items: flex-start; gap: .8rem;
                 padding: .65rem 0; border-bottom: 1px solid #2d2a45; }
.pipeline-step:last-child { border-bottom: none; }
.step-num { min-width: 28px; height: 28px; background: #7C3AED; border-radius: 50%;
            display: flex; align-items: center; justify-content: center;
            font-size: .75rem; font-weight: 700; color: #fff;
            flex-shrink: 0; margin-top: .1rem; }
.step-text { font-size: .9rem; color: #d1d5db; }
.step-text strong { color: #e8e8f0; }
</style>
""", unsafe_allow_html=True)


# ──────────────────────────────────────────────
# MODEL LOADING  (Streamlit-layer concern)
# ──────────────────────────────────────────────
@st.cache_resource(show_spinner="Loading VaniGuard model…")
def _load_model_cached():
    return load_model()


session, _model_error = _load_model_cached()


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
            [" Dashboard", " Analyze", " Live Monitor", " History"],
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
            st.info("⚠️ Predictions will be **random** until the model is loaded.")

        st.markdown("<hr class='section-rule'>", unsafe_allow_html=True)
        if _MINIAUDIO_OK:
            st.success("MP3/WAV/FLAC/OGG supported")
        else:
            st.warning("MP3 not supported — WAV/FLAC/OGG only")
            st.caption("Install miniaudio for MP3 support:\n`pip install miniaudio`")

    return page  # type: ignore[return-value]


# ──────────────────────────────────────────────
# PAGE — DASHBOARD
# ──────────────────────────────────────────────
def render_dashboard() -> None:
    st.markdown("# Dashboard")
    st.markdown(
        "Welcome to **VaniGuard** — a robust AI voice-clone detector tailored for Indian languages."
    )
    st.markdown("<hr class='section-rule'>", unsafe_allow_html=True)

    df = load_history()
    total = len(df)
    n_ai = len(df[df["Verdict"].str.contains("AI-Generated", na=False)]) if total else 0
    n_human = len(df[df["Verdict"].str.contains("Human", na=False)]) if total else 0
    avg_conf = df["Confidence (%)"].mean() if total else 0.0
    ai_rate = (n_ai / total * 100) if total else 0.0

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Clips Analyzed",    total)
    c2.metric("AI Detected",       n_ai)
    c3.metric("Human",             n_human)
    c4.metric("AI Detection Rate", f"{ai_rate:.1f}%")
    c5.metric("Avg Confidence",    f"{avg_conf:.1f}%")

    st.markdown("<hr class='section-rule'>", unsafe_allow_html=True)

    col_left, col_right = st.columns([1, 1], gap="large")

    with col_left:
        st.markdown("### How It Works")
        steps = [
            ("Audio Ingestion",    "File is uploaded and decoded by <b>miniaudio / soundfile</b>."),
            ("Resampling",         "Audio is resampled to <b>16 kHz</b> mono."),
            ("Trim / Pad",         "Clip is trimmed or zero-padded to exactly <b>3.0 seconds</b>."),
            ("Feature Extraction", "A <b>Log-Mel Spectrogram</b> is computed (128 bands, FFT 1024)."),
            ("Normalisation",      "Spectrogram is <b>min-max normalised</b> to [0, 1]."),
            ("Inference",          "<b>MobileNetV2 (ONNX)</b> outputs P(AI-generated) ∈ [0, 1]."),
            ("Classification",     "Probability is mapped to a <b>verdict + risk band</b>."),
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
            ("HIGH RISK",  "risk-high",     "P(AI) ≥ 0.80 — very likely synthetic"),
            ("SUSPICIOUS", "risk-sus",       "P(AI) ≥ 0.60 — possibly synthetic"),
            ("UNCERTAIN",  "risk-uncertain", "P(AI) ∈ [0.40, 0.60) — review advised"),
            ("LOW RISK",   "risk-low",       "P(AI) < 0.40 — likely human"),
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
def render_analyze() -> None:
    st.markdown("# Analyze Audio")
    st.markdown(
        "Upload an audio clip to determine whether the voice is **human** or **AI-generated**."
    )
    st.markdown("<hr class='section-rule'>", unsafe_allow_html=True)

    # ── Model-unavailable banner (visible on this page, not just sidebar) ──
    if session is None:
        st.warning(
            "⚠️ **Model not loaded** — results below are **random placeholders**, "
            "not real predictions. Check the sidebar for the error detail."
        )

    uploaded = st.file_uploader(
        "Choose an audio file",
        type=["wav", "mp3", "ogg", "flac", "m4a"],
        help=f"Supported: WAV, MP3, OGG, FLAC, M4A · Max {_MAX_UPLOAD_MB} MB",
    )

    if uploaded is None:
        st.info("Upload an audio file above to get started.")
        return

    # ── Server-side size validation ────────────────────────────────────────
    if uploaded.size > _MAX_UPLOAD_MB * 1024 * 1024:
        st.error(
            f"File is too large ({uploaded.size / 1024 / 1024:.1f} MB). "
            f"Maximum allowed size is {_MAX_UPLOAD_MB} MB."
        )
        return

    ext = uploaded.name.rsplit(".", 1)[-1].lower()
    st.audio(uploaded, format=f"audio/{ext}")
    st.markdown(f"**File:** `{uploaded.name}` &nbsp;·&nbsp; **Size:** {uploaded.size / 1024:.1f} KB")

    if not st.button("Run Detection", type="primary", use_container_width=False):
        return

    # ── Fully in-memory pipeline ───────────────────────────────────────────
    audio_bytes = uploaded.getvalue()
    try:
        with st.spinner("Analysing audio…"):
            mel_norm, mel_tensor, duration_s = preprocess_audio(audio_bytes, ext)
            prob_ai = run_inference(session, mel_tensor)
    except (ValueError, RuntimeError) as exc:
        st.error(f"{exc}")
        return
    except Exception as exc:
        st.error(f"Unexpected error processing audio: {exc}")
        return

    # ── Classification ────────────────────────────────────────────────────
    verdict, risk_band, risk_css = classify(prob_ai)
    is_ai = "AI-Generated" in verdict
    confidence = prob_ai if is_ai else (1.0 - prob_ai)
    confidence_pct = confidence * 100

    # ── Verdict banner ────────────────────────────────────────────────────
    if is_ai:
        st.markdown(
            "<div class='verdict-ai'>"
            "<p class='verdict-title'>AI-Generated Voice Detected</p>"
            "<p class='verdict-sub'>This clip has characteristics consistent with synthetic speech.</p>"
            "</div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            "<div class='verdict-human'>"
            "<p class='verdict-title'>Human Voice Verified</p>"
            "<p class='verdict-sub'>This clip appears to be authentic human speech.</p>"
            "</div>",
            unsafe_allow_html=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Metrics row ───────────────────────────────────────────────────────
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Verdict",        verdict)
    m2.metric("AI Probability", f"{prob_ai * 100:.1f}%")
    m3.metric("Confidence",     f"{confidence_pct:.1f}%")
    m4.metric("Duration",       f"{duration_s:.2f} s")

    st.markdown(
        f"<div style='margin:.6rem 0'>"
        f"<span class='risk-badge {risk_css}'>{risk_band}</span>"
        f"</div>",
        unsafe_allow_html=True,
    )
    st.progress(float(confidence), text=f"Confidence: {confidence_pct:.1f}%")

    # ── Mel Spectrogram ───────────────────────────────────────────────────
    with st.expander("View Mel Spectrogram", expanded=False):
        fig, ax = plt.subplots(figsize=(10, 3))
        fig.patch.set_facecolor("#1a1826")
        ax.set_facecolor("#1a1826")
        img = librosa.display.specshow(
            mel_norm, sr=SAMPLE_RATE, hop_length=HOP_LENGTH,
            x_axis="time", y_axis="mel", ax=ax, cmap="magma",
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
    try:
        save_to_history(uploaded.name, verdict, confidence_pct, risk_band, prob_ai)
        st.caption("Result saved to history.")
    except Exception as exc:
        st.warning(f"Could not save to history: {exc}")


# ──────────────────────────────────────────────
# PAGE — LIVE MONITOR
# ──────────────────────────────────────────────
def render_live_monitor() -> None:
    import time
    import pandas as pd
    from src.risk_engine import RiskEngine
    from src.pipeline import StreamPipeline
    from src.audio_io import _decode_audio_bytes
    from src.config import SAMPLE_RATE, EER_THRESHOLD, THRESH_HIGH

    st.markdown("# Live Monitor")
    st.markdown("Analyze continuous audio to detect sustained AI voice risks.")
    st.markdown("<hr class='section-rule'>", unsafe_allow_html=True)

    if session is None:
        st.warning("⚠️ Model not loaded. Predictions will be random placeholders.")

    # ── State Init ──
    if "live_history" not in st.session_state:
        st.session_state.live_history = []
    if "live_table" not in st.session_state:
        st.session_state.live_table = []
    if "live_is_running" not in st.session_state:
        st.session_state.live_is_running = False

    # ── Settings Sidebar ──
    with st.sidebar.expander("⚙️ Live Monitor Settings", expanded=True):
        st.markdown("**Dynamic Thresholds**")
        amber_thresh = st.slider("Amber Threshold (EER)", 0.0, 1.0, float(EER_THRESHOLD), 0.01)
        red_thresh = st.slider("Red Threshold (High Risk)", 0.0, 1.0, float(THRESH_HIGH), 0.01)

    uploaded = st.file_uploader(
        "Choose an audio file for live simulation",
        type=["wav", "mp3", "ogg", "flac", "m4a"],
        key="live_monitor_upload"
    )

    if uploaded is None:
        st.info("Upload an audio file to start live monitoring.")
        st.session_state.live_history = []
        st.session_state.live_table = []
        st.session_state.live_is_running = False
        return

    ext = uploaded.name.rsplit(".", 1)[-1].lower()

    col1, col2 = st.columns([1, 5])
    with col1:
        start_btn = st.button("▶ Start", type="primary", use_container_width=True)
    with col2:
        stop_btn = st.button("⏹ Stop", use_container_width=False)

    if stop_btn:
        st.session_state.live_is_running = False

    if start_btn:
        st.session_state.live_history = []
        st.session_state.live_table = []
        st.session_state.live_is_running = True
        
    st.markdown("### Risk Status")
    badge_placeholder = st.empty()
    
    st.markdown("### Window Analysis")
    chart_placeholder = st.empty()
    table_placeholder = st.empty()

    # Re-render existing state if not running (e.g. after hitting Stop)
    if not st.session_state.live_is_running and st.session_state.live_table:
        latest = st.session_state.live_table[-1]
        lvl = latest["Level"]
        conf = latest["Confidence"]
        msg = f"**Status:** {lvl} &nbsp;&nbsp;|&nbsp;&nbsp; **Confidence:** {conf:.1f}%"
        with badge_placeholder.container():
            if lvl == "GREEN":
                st.success(msg)
            elif lvl == "AMBER":
                st.warning(msg)
            else:
                st.error(msg)
        chart_placeholder.line_chart(st.session_state.live_history, y_label="P(AI)", height=300)
        table_placeholder.dataframe(pd.DataFrame(st.session_state.live_table), use_container_width=True)

    if st.session_state.live_is_running:
        audio_bytes = uploaded.getvalue()
        try:
            pcm = _decode_audio_bytes(audio_bytes, ext)
        except Exception as exc:
            st.error(f"Error decoding audio: {exc}")
            st.session_state.live_is_running = False
            return
            
        sp = StreamPipeline(session=session)
        engine = RiskEngine(amber_threshold=amber_thresh, red_threshold=red_thresh)
        engine.reset()
        
        # 1-second chunks (since hop size is 1 second, this produces exactly 1 result per chunk smoothly)
        chunk_size = int(SAMPLE_RATE * 1.0) 
        
        for i in range(0, len(pcm), chunk_size):
            # If user clicked stop, Streamlit raises StopException and aborts the loop,
            # but we also check our own flag just in case.
            if not st.session_state.live_is_running:
                break
                
            chunk = pcm[i:i+chunk_size]
            results = sp.write(chunk)
            if i + chunk_size >= len(pcm):
                results.extend(sp.flush())
                
            for r in results:
                state = engine.ingest(r.prob_ai)
                
                st.session_state.live_history.append(r.prob_ai)
                if len(st.session_state.live_history) > 5:
                    st.session_state.live_history.pop(0)
                
                win_time = f"{r.window_index}s - {r.window_index + 4}s"
                
                st.session_state.live_table.append({
                    "Time": win_time,
                    "P(AI)": round(r.prob_ai, 3),
                    "Verdict": r.verdict,
                    "Level": state.level.name,
                    "Confidence": state.confidence * 100
                })
                    
                # Update UI elements
                lvl = state.level.name
                msg = f"**Status:** {lvl} &nbsp;&nbsp;|&nbsp;&nbsp; **Confidence:** {state.confidence*100:.1f}%"
                with badge_placeholder.container():
                    if lvl == "GREEN":
                        st.success(msg)
                    elif lvl == "AMBER":
                        st.warning(msg)
                    else:
                        st.error(msg)
                
                chart_placeholder.line_chart(st.session_state.live_history, y_label="P(AI)", height=300)
                
                df_table = pd.DataFrame(st.session_state.live_table)
                table_placeholder.dataframe(df_table.iloc[::-1], use_container_width=True) # Show newest first
                
                time.sleep(0.8) # 0.8s sleep to simulate 1s hop speed while allowing UI overhead
                
        st.session_state.live_is_running = False
        st.info("Live monitor playback complete.")
        
        # We trigger a rerun so the state stabilizes and buttons reset
        st.rerun()

# ──────────────────────────────────────────────
# PAGE — HISTORY
# ──────────────────────────────────────────────
def render_history() -> None:
    st.markdown("# Detection History")
    st.markdown("<hr class='section-rule'>", unsafe_allow_html=True)

    df = load_history()
    if df.empty:
        st.info("No history yet. Analyze some audio files first.")
        return

    df_display = df.iloc[::-1].reset_index(drop=True)

    total = len(df)
    n_ai = df["Verdict"].str.contains("AI-Generated", na=False).sum()
    n_human = df["Verdict"].str.contains("Human", na=False).sum()

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Analyzed", total)
    c2.metric("AI Detected",    int(n_ai))
    c3.metric("Human",          int(n_human))

    st.markdown("<br>", unsafe_allow_html=True)

    def style_verdict(val: str) -> str:
        if "AI" in str(val):
            return "color: #fca5a5; font-weight: 600"
        if "Human" in str(val):
            return "color: #86efac; font-weight: 600"
        return "color: #fde68a"

    styled = df_display.style.map(style_verdict, subset=["Verdict"])
    st.dataframe(styled, use_container_width=True, height=400)

    col_dl, col_clr, _ = st.columns([1, 1, 4])
    with col_dl:
        csv_bytes = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "Download CSV", data=csv_bytes,
            file_name="vaniguard_history.csv", mime="text/csv",
            use_container_width=True,
        )
    with col_clr:
        if st.button("Clear History", use_container_width=True):
            try:
                clear_history()
                st.success("History cleared.")
                st.rerun()
            except Exception as exc:
                st.error(f"Could not clear history: {exc}")


# ──────────────────────────────────────────────
# ENTRY POINT
# ──────────────────────────────────────────────
def main() -> None:
    page = render_sidebar()

    if "Dashboard" in page:
        render_dashboard()
    elif "Analyze" in page:
        render_analyze()
    elif "Live Monitor" in page:
        render_live_monitor()
    elif "History" in page:
        render_history()


if __name__ == "__main__":
    main()
