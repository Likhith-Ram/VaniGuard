from fastapi.testclient import TestClient
from api.main import app
import numpy as np
import io
import wave
import struct

client = TestClient(app)

def create_dummy_wav():
    """Create a short, dummy valid 16kHz WAV file in memory."""
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        # write 16000 samples (1 sec)
        data = np.zeros(16000, dtype=np.int16)
        wf.writeframes(data.tobytes())
    buf.seek(0)
    return buf

def test_history():
    response = client.get("/history")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_analyze():
    # Make a dummy wav file
    wav_buf = create_dummy_wav()
    
    response = client.post(
        "/analyze",
        files={"file": ("test.wav", wav_buf, "audio/wav")}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "verdict" in data
    assert "confidence" in data
    assert "risk_band" in data
    assert "prob_ai" in data
