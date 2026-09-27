import { Link } from 'react-router-dom';

export default function NotFound() {
  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'var(--bg-dark)',
        color: 'var(--text)',
        textAlign: 'center',
        padding: '2rem',
      }}
    >
      <div style={{ fontSize: '5rem', marginBottom: '1rem' }}>🎙️</div>
      <h1
        style={{
          fontSize: '6rem',
          fontWeight: 800,
          background: 'linear-gradient(135deg, #7c3aed, #a78bfa)',
          WebkitBackgroundClip: 'text',
          WebkitTextFillColor: 'transparent',
          lineHeight: 1,
          marginBottom: '1rem',
        }}
      >
        404
      </h1>
      <p
        style={{
          fontSize: '1.25rem',
          color: 'var(--text-muted)',
          maxWidth: '480px',
          marginBottom: '2.5rem',
        }}
      >
        This page doesn&apos;t exist — but our AI voice detector is still
        listening.
      </p>
      <Link
        to="/analyze"
        className="btn"
        style={{ textDecoration: 'none', display: 'inline-block' }}
        aria-label="Go back to Analyze page"
      >
        ← Back to Analyze
      </Link>
    </div>
  );
}
