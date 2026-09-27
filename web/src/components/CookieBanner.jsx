import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';

const STORAGE_KEY = 'vg_cookie_consent';

export default function CookieBanner() {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    // Only show if the user has not yet consented
    if (!localStorage.getItem(STORAGE_KEY)) {
      // Small delay so it doesn't flash on first paint
      const t = setTimeout(() => setVisible(true), 800);
      return () => clearTimeout(t);
    }
  }, []);

  const accept = () => {
    localStorage.setItem(STORAGE_KEY, 'accepted');
    setVisible(false);
  };

  const decline = () => {
    localStorage.setItem(STORAGE_KEY, 'declined');
    setVisible(false);
  };

  if (!visible) return null;

  return (
    <div
      role="dialog"
      aria-live="polite"
      aria-label="Cookie consent banner"
      style={{
        position: 'fixed',
        bottom: '4.5rem', // above mobile nav bar
        left: '1rem',
        right: '1rem',
        maxWidth: '520px',
        margin: '0 auto',
        background: '#1e1b2e',
        border: '1px solid #2d2a45',
        borderRadius: '14px',
        padding: '1.25rem 1.5rem',
        boxShadow: '0 8px 40px rgba(0,0,0,0.4)',
        zIndex: 200,
        display: 'flex',
        flexDirection: 'column',
        gap: '1rem',
      }}
    >
      <p style={{ color: '#e8e8f0', fontSize: '0.9rem', lineHeight: 1.6 }}>
        🍪 VaniGuard uses cookies to remember your preferences and improve your
        experience. See our{' '}
        <Link to="/privacy" style={{ color: '#7c3aed', textDecoration: 'underline' }}>
          Privacy Policy
        </Link>
        .
      </p>
      <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'flex-end' }}>
        <button
          onClick={decline}
          aria-label="Decline cookies"
          style={{
            background: 'transparent',
            border: '1px solid #2d2a45',
            color: '#9ca3af',
            borderRadius: '8px',
            padding: '0.5rem 1.1rem',
            cursor: 'pointer',
            fontSize: '0.85rem',
          }}
        >
          Decline
        </button>
        <button
          onClick={accept}
          aria-label="Accept cookies"
          className="btn"
          style={{ padding: '0.5rem 1.25rem', fontSize: '0.85rem' }}
        >
          Accept
        </button>
      </div>
    </div>
  );
}
