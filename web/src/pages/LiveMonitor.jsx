import { useEffect, useState, useRef } from 'react';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend
} from 'chart.js';
import { Line } from 'react-chartjs-2';

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend);

const WS_URL = import.meta.env.VITE_WS_URL;

export default function LiveMonitor() {
  const [file, setFile] = useState(null);
  const [isRunning, setIsRunning] = useState(false);
  const [history, setHistory] = useState([]); // For chart
  const [currentStatus, setCurrentStatus] = useState(null);
  
  const wsRef = useRef(null);

  const startMonitor = async () => {
    if (!file) return;
    
    // Read file as ArrayBuffer
    const buffer = await file.arrayBuffer();
    
    setIsRunning(true);
    setHistory([]);
    setCurrentStatus(null);
    
    wsRef.current = new WebSocket(`${WS_URL}/stream`);
    
    wsRef.current.onopen = () => {
      // Send audio data in chunks to simulate live streaming
      // In a real app with mic, we'd stream via AudioContext
      const CHUNK_SIZE = 16000 * 4; // 4 bytes (float32) * 16000 = 1 sec
      let offset = 0;
      
      const interval = setInterval(() => {
        if (wsRef.current?.readyState !== WebSocket.OPEN) {
          clearInterval(interval);
          return;
        }
        
        if (offset >= buffer.byteLength) {
          clearInterval(interval);
          wsRef.current.close();
          setIsRunning(false);
          return;
        }
        
        const chunk = buffer.slice(offset, offset + CHUNK_SIZE);
        wsRef.current.send(chunk);
        offset += CHUNK_SIZE;
      }, 1000); // 1 chunk per second
    };
    
    wsRef.current.onmessage = (event) => {
      const data = JSON.parse(event.data);
      setCurrentStatus({
        level: data.status_level,
        confidence: data.status_confidence
      });
      setHistory(prev => {
        const newHist = [...prev, { time: data.window_index, prob_ai: data.prob_ai }];
        if (newHist.length > 5) return newHist.slice(newHist.length - 5);
        return newHist;
      });
    };
    
    wsRef.current.onclose = () => {
      setIsRunning(false);
    };
  };

  const stopMonitor = () => {
    if (wsRef.current) {
      wsRef.current.close();
    }
    setIsRunning(false);
  };

  return (
    <div>
      <h1>Live Monitor</h1>
      <p style={{ color: 'var(--text-muted)', marginBottom: '2rem' }}>
        Analyze continuous audio to detect sustained AI voice risks.
      </p>

      <div className="card">
        <input 
          type="file" 
          className="file-input" 
          accept="audio/*"
          onChange={(e) => setFile(e.target.files[0])}
          disabled={isRunning}
        />
        <div style={{ display: 'flex', gap: '1rem' }}>
          <button className="btn" onClick={startMonitor} disabled={!file || isRunning}>
            ▶ Start
          </button>
          <button className="btn" onClick={stopMonitor} disabled={!isRunning} style={{ backgroundColor: '#374151' }}>
            ⏹ Stop
          </button>
        </div>
      </div>

      <div className="card">
        <h2>Risk Status</h2>
        {currentStatus ? (
          <div className={`badge badge-${currentStatus.level === 'GREEN' ? 'green' : currentStatus.level === 'AMBER' ? 'amber' : 'red'}`} style={{ fontSize: '1.2rem', padding: '0.75rem 1.5rem' }}>
            Status: {currentStatus.level} | Confidence: {(currentStatus.confidence * 100).toFixed(1)}%
          </div>
        ) : (
          <p style={{ color: 'var(--text-muted)' }}>Waiting for data...</p>
        )}
      </div>

      <div className="card">
        <h2>Last 5 Windows AI Probability</h2>
        <div style={{ height: '300px', width: '100%', marginTop: '1rem' }}>
          <Line 
            data={{
              labels: history.map(h => h.time),
              datasets: [
                {
                  label: 'P(AI)',
                  data: history.map(h => h.prob_ai),
                  borderColor: '#7c3aed',
                  backgroundColor: 'rgba(124, 58, 237, 0.5)',
                  borderWidth: 3,
                  pointRadius: 6,
                }
              ]
            }} 
            options={{
              responsive: true,
              maintainAspectRatio: false,
              scales: {
                y: { min: 0, max: 1, grid: { color: '#2d2a45' } },
                x: { grid: { color: '#2d2a45' } }
              },
              plugins: { legend: { display: false } }
            }}
          />
        </div>
      </div>
    </div>
  );
}
