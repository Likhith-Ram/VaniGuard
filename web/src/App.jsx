import { BrowserRouter as Router, Routes, Route, NavLink, Navigate } from 'react-router-dom';
import Analyze from './pages/Analyze';
import LiveMonitor from './pages/LiveMonitor';
import History from './pages/History';
import './index.css';

function App() {
  return (
    <Router>
      <div className="app-container">
        <aside className="sidebar">
          <div className="sidebar-title">🎙️ Vani<span>Guard</span></div>
          <nav className="nav-links">
            <NavLink to="/analyze" className={({isActive}) => isActive ? "nav-link active" : "nav-link"}>Analyze</NavLink>
            <NavLink to="/live" className={({isActive}) => isActive ? "nav-link active" : "nav-link"}>Live Monitor</NavLink>
            <NavLink to="/history" className={({isActive}) => isActive ? "nav-link active" : "nav-link"}>History</NavLink>
          </nav>
        </aside>
        
        <main className="main-content">
          <Routes>
            <Route path="/" element={<Navigate to="/analyze" replace />} />
            <Route path="/analyze" element={<Analyze />} />
            <Route path="/live" element={<LiveMonitor />} />
            <Route path="/history" element={<History />} />
          </Routes>
        </main>
      </div>
    </Router>
  );
}

export default App;
