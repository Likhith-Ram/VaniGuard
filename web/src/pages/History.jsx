import { useEffect, useState } from 'react';

const API_URL = import.meta.env.VITE_API_URL;

export default function History() {
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchHistory = async () => {
      try {
        const res = await fetch(`${API_URL}/history`);
        if (!res.ok) throw new Error('Failed to fetch history');
        const data = await res.json();
        setHistory(data);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };
    fetchHistory();
  }, []);

  return (
    <div>
      <h1>History</h1>
      <p style={{ color: 'var(--text-muted)', marginBottom: '2rem' }}>
        Log of all previously analyzed audio files.
      </p>

      <div className="card">
        {loading ? (
          <p>Loading history...</p>
        ) : error ? (
          <p style={{ color: '#ef4444' }}>{error}</p>
        ) : history.length === 0 ? (
          <p style={{ color: 'var(--text-muted)' }}>No history found.</p>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table>
              <thead>
                <tr>
                  <th>Timestamp</th>
                  <th>Filename</th>
                  <th>Verdict</th>
                  <th>Confidence (%)</th>
                  <th>Risk Band</th>
                  <th>P(AI)</th>
                </tr>
              </thead>
              <tbody>
                {history.reverse().map((row, i) => (
                  <tr key={i}>
                    <td>{row.Timestamp}</td>
                    <td>{row.Filename}</td>
                    <td>{row.Verdict}</td>
                    <td>{row['Confidence (%)']?.toFixed(2) || '-'}</td>
                    <td>
                      <span className={`badge ${row['Risk CSS'] === 'risk-high' ? 'badge-red' : row['Risk CSS'] === 'risk-sus' ? 'badge-amber' : 'badge-green'}`}>
                        {row['Risk Band']}
                      </span>
                    </td>
                    <td>{row['P(AI)']?.toFixed(3) || '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
