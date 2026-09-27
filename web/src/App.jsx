import { BrowserRouter as Router, Routes, Route, NavLink, Navigate, Link, useLocation } from 'react-router-dom';
import { useEffect } from 'react';
import Analyze from './pages/Analyze';
import LiveMonitor from './pages/LiveMonitor';
import History from './pages/History';
import NotFound from './pages/NotFound';
import ThankYou from './pages/ThankYou';
import Privacy from './pages/Privacy';
import Terms from './pages/Terms';
import CookieBanner from './components/CookieBanner';
import { trackPageView } from './lib/analytics';
import './index.css';

// Tracks a page view on every route change
function AnalyticsTracker() {
  const { pathname } = useLocation();
  useEffect(() => { trackPageView(pathname); }, [pathname]);
  return null;
}

function App() {
  return (
    <Router>
      <div className="app-container">
        <AnalyticsTracker />
        <aside className="sidebar" role="navigation" aria-label="Main navigation">
          <div className="sidebar-title">
            <span role="img" aria-label="Microphone">🎙️</span> Vani<span>Guard</span>
          </div>
          <nav className="nav-links">
            <NavLink to="/analyze" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>
              Analyze
            </NavLink>
            <NavLink to="/live" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>
              Live Monitor
            </NavLink>
            <NavLink to="/history" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>
              History
            </NavLink>
          </nav>

          {/* Footer links (desktop only — hidden on mobile bottom nav) */}
          <div className="sidebar-footer">
            <Link to="/privacy" className="sidebar-footer-link">Privacy Policy</Link>
            <Link to="/terms" className="sidebar-footer-link">Terms</Link>
          </div>
        </aside>

        <main className="main-content">
          <Routes>
            <Route path="/" element={<Navigate to="/analyze" replace />} />
            <Route path="/analyze" element={<Analyze />} />
            <Route path="/live" element={<LiveMonitor />} />
            <Route path="/history" element={<History />} />
            <Route path="/thank-you" element={<ThankYou />} />
            <Route path="/privacy" element={<Privacy />} />
            <Route path="/terms" element={<Terms />} />
            <Route path="*" element={<NotFound />} />
          </Routes>
        </main>
        <CookieBanner />
      </div>
    </Router>
  );
}

export default App;
