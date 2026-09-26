import { useState } from 'react';

const API_URL = import.meta.env.VITE_API_URL;

export default function Analyze() {
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

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
      if (!res.ok) throw new Error('Failed to analyze audio');
      const data = await res.json();
      setResult(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <h1>Analyze Audio</h1>
      <p style={{ color: 'var(--text-muted)', marginBottom: '2rem' }}>
        Upload an audio clip to determine whether the voice is human or AI-generated.
      </p>

      <div className="card">
        <div className="file-input-wrapper">
          <input 
            type="file" 
            className="file-input" 
            accept="audio/*"
            onChange={(e) => setFile(e.target.files[0])}
          />
        </div>
        <button 
          className="btn" 
          onClick={handleAnalyze} 
          disabled={!file || loading}
        >
          {loading ? 'Analyzing...' : 'Run Detection'}
        </button>

        {error && <p style={{ color: '#ef4444', marginTop: '1rem' }}>{error}</p>}
      </div>

      {result && (
        <div className="card">
          <h2>Analysis Result</h2>
          <div style={{ display: 'flex', gap: '2rem', marginTop: '1.5rem' }}>
            <div>
              <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>Verdict</p>
              <p style={{ fontSize: '1.5rem', fontWeight: 600 }}>{result.verdict}</p>
            </div>
            <div>
              <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>Confidence</p>
              <p style={{ fontSize: '1.5rem', fontWeight: 600 }}>{result.confidence.toFixed(1)}%</p>
            </div>
            <div>
              <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>Risk Level</p>
              <div className={`badge ${result.risk_css === 'risk-high' ? 'badge-red' : result.risk_css === 'risk-sus' ? 'badge-amber' : result.risk_css === 'risk-low' ? 'badge-green' : 'badge-amber'}`}>
                {result.risk_band}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
