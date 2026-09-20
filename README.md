# VaniGuard — Deep Audio Cloning Detection

VaniGuard is an audio deepfake detection application designed to identify AI-generated voices (specifically focusing on Hindi, Tamil, and Telugu audio). It utilizes signal processing, a fine-tuned MobileNetV2 model, and a Streamlit dashboard.

## 👥 Academic Team

This project was developed by a 6-member academic team. 

## 🏗️ System Architecture

The application is built with a fully in-memory data pipeline—requiring no temporary files or external binaries like ffmpeg.

1. **Browser Upload**: Receives the raw audio bytes from the user.
2. **Audio Decoding**: `miniaudio.decode()` processes MP3, WAV, FLAC, OGG, or M4A formats natively.
3. **Signal Processing**: `librosa` transforms the numpy float32 PCM array (resample → trim/pad → melspectrogram → power_to_db → min-max norm).
4. **Inference**: A fine-tuned MobileNetV2 model deployed via ONNX inference (`vaniguard.onnx`) predicts the probability of the audio being AI-generated.
5. **Verdict & Dashboard**: Streamlit displays the verdict, confidence score, risk band, and data visualizations.

## 🚀 Local Setup Instructions

### Prerequisites
- Python 3.9+
- Git

### Installation

1. **Clone the repository:**
   ```bash
   git clone <repository_url>
   cd VaniGuard
   ```

2. **Create and activate a virtual environment:**
   ```bash
   python -m venv venv
   
   # On Windows:
   venv\Scripts\activate
   # On Unix or MacOS:
   source venv/bin/activate
   ```

3. **Install the dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

### Running the Application

1. Ensure your virtual environment is active.
2. Run the Streamlit application:
   ```bash
   cd ui
   streamlit run app.py
   ```
   *Alternatively, on Windows, you can just run `run.bat` in the root folder if configured.*
