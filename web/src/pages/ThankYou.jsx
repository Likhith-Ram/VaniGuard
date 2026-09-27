import { Link } from 'react-router-dom';
import useDocTitle from '../hooks/useDocTitle';

export default function ThankYou() {
  useDocTitle('Thank You');

  return (
    <div
      style={{
        minHeight: '70vh',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        textAlign: 'center',
        padding: '3rem 2rem',
      }}
    >
      <div style={{ fontSize: '4rem', marginBottom: '1.25rem' }}>
        <span role="img" aria-label="Party popper">🎉</span>
      </div>
      <h1 style={{ marginBottom: '1rem' }}>Thank You!</h1>
      <p style={{ color: 'var(--text-muted)', maxWidth: '480px', marginBottom: '2rem' }}>
        Your audio has been analyzed. VaniGuard has recorded the result in
        your detection history. Stay vigilant — AI voices are getting better
        every day.
      </p>
      <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap', justifyContent: 'center' }}>
        <Link
          to="/analyze"
          className="btn"
          style={{ textDecoration: 'none' }}
          aria-label="Analyze another audio file"
        >
          Analyze Another
        </Link>
        <Link
          to="/history"
          className="btn"
          style={{ textDecoration: 'none', background: 'transparent', border: '1px solid var(--border)', color: 'var(--text)' }}
          aria-label="View your detection history"
        >
          View History
        </Link>
      </div>
    </div>
  );
}
