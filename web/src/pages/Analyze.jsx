import { useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import useDocTitle from '../hooks/useDocTitle';

const API_URL = import.meta.env.VITE_API_URL;

export default function Analyze() {
  useDocTitle('Analyze Audio');
  const navigate = useNavigate();
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef(null);

  const handleAnalyze = async () => {
    if (!file) return;
    setLoading(true);
    setError(null);
    setResult(null);

    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await fetch(`${API_URL}/analyze`, {
        method: 'POST',
        body: formData,
      });
      if (!res.ok) throw new Error('Failed to analyze audio. Please try again.');
      const data = await res.json();
      setResult(data);
      navigate('/thank-you');
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    const dropped = e.dataTransfer.files[0];
    if (dropped && dropped.type.startsWith('audio/')) setFile(dropped);
  };

  const riskBadgeClass = (css) => {
    if (css === 'risk-high') return 'badge badge-red';
    if (css === 'risk-sus') return 'badge badge-amber';
    if (css === 'risk-low') return 'badge badge-green';
    return 'badge badge-amber';
  };

  return (
    <div>
      {/* ── Hero / CTA above the fold ── */}
      <div className="hero-cta" aria-label="Analyze audio section">
        <div className="hero-cta-text">
          <h1>Detect AI-Cloned Voices</h1>
          <p>
            Drop any audio clip below and our MobileNetV2 model will tell you
            in seconds whether it&apos;s a real human voice or a synthetic
            clone.
          </p>
        </div>

        {/* Drop zone + primary CTA */}
        <div
          className={`drop-zone card${dragOver ? ' drop-zone--active' : ''}${file ? ' drop-zone--has-file' : ''}`}
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
          onClick={() => !file && fileInputRef.current?.click()}
          role="button"
          tabIndex={0}
          aria-label="Audio file drop zone — click or drag and drop"
          onKeyDown={(e) => e.key === 'Enter' && !file && fileInputRef.current?.click()}
        >
          <input
            ref={fileInputRef}
            id="audio-file-input"
            type="file"
            className="file-input"
            accept="audio/*"
            aria-label="Select audio file for analysis"
            onChange={(e) => setFile(e.target.files[0])}
            style={{ display: 'none' }}
          />

          {file ? (
            <div className="drop-zone-file-info">
              <span className="drop-zone-icon" aria-hidden="true">🎵</span>
              <span className="drop-zone-filename">{file.name}</span>
              <button
                className="drop-zone-clear"
                onClick={(e) => { e.stopPropagation(); setFile(null); setResult(null); setError(null); }}
                aria-label="Remove selected file"
              >
                ✕
              </button>
            </div>
          ) : (
            <div className="drop-zone-placeholder">
              <span className="drop-zone-icon" aria-hidden="true">🎙️</span>
              <p>Drag &amp; drop an audio file here, or <strong>click to browse</strong></p>
              <p className="drop-zone-hint">Supports MP3, WAV, FLAC, OGG, M4A</p>
            </div>
          )}
        </div>

        <button
          id="run-detection-btn"
          className="btn btn-cta in-page-only"
          onClick={handleAnalyze}
          disabled={!file || loading}
          aria-busy={loading}
          aria-label={loading ? 'Analyzing audio…' : 'Run AI voice detection'}
        >
          {loading ? (
            <>
              <span className="spinner" aria-hidden="true" />
              Analyzing&hellip;
            </>
          ) : (
            '🔍  Run Detection'
          )}
        </button>

        {/* Form error state */}
        {error && (
          <div className="form-error" role="alert" aria-live="assertive">
            <span aria-hidden="true">⚠️</span> {error}
          </div>
        )}
      </div>

      {/* ── Result card ── */}
      {result && (
        <div className="card result-card" aria-label="Analysis result" aria-live="polite">
          <h2>Analysis Result</h2>
          <div className="result-grid">
            <div className="result-stat">
              <p className="result-label">Verdict</p>
              <p className="result-value">{result.verdict}</p>
            </div>
            <div className="result-stat">
              <p className="result-label">Confidence</p>
              <p className="result-value">{(result.confidence * 100).toFixed(1)}%</p>
            </div>
            <div className="result-stat">
              <p className="result-label">Duration</p>
              <p className="result-value">{result.duration_s?.toFixed(1)}s</p>
            </div>
            <div className="result-stat">
              <p className="result-label">Risk Level</p>
              <div className={riskBadgeClass(result.risk_css)}>
                {result.risk_band}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── Sticky mobile CTA (visible only on narrow screens) ── */}
      <div className="sticky-cta-bar">
        <button
          className="btn btn-cta"
          onClick={handleAnalyze}
          disabled={!file || loading}
          aria-busy={loading}
          aria-label={loading ? 'Analyzing audio…' : 'Run AI voice detection'}
        >
          {loading ? (
            <><span className="spinner" aria-hidden="true" /> Analyzing&hellip;</>
          ) : (
            '🔍  Run Detection'
          )}
        </button>
      </div>
    </div>
  );
}
