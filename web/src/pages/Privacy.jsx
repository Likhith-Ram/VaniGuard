import useDocTitle from '../hooks/useDocTitle';

export default function Privacy() {
  useDocTitle('Privacy Policy');

  return (
    <div style={{ maxWidth: '760px', margin: '0 auto' }}>
      <h1>Privacy Policy</h1>
      <p style={{ color: 'var(--text-muted)', marginBottom: '2rem' }}>
        Last updated: 27 September 2026
      </p>

      <div className="card">
        <h2>1. What We Collect</h2>
        <p style={{ color: 'var(--text-muted)', marginBottom: '1rem' }}>
          VaniGuard processes audio files you upload solely to perform
          AI-voice detection. We do <strong>not</strong> store the raw audio
          bytes after analysis is complete. We store only the detection result
          (verdict, confidence score, risk band, and timestamp) in a local
          history log.
        </p>
        <h2>2. How We Use Your Data</h2>
        <p style={{ color: 'var(--text-muted)', marginBottom: '1rem' }}>
          Detection history is stored locally on the server running VaniGuard
          and is used solely to display your past results. We do not share,
          sell, or transmit your audio or results to any third party.
        </p>
        <h2>3. Cookies & Analytics</h2>
        <p style={{ color: 'var(--text-muted)', marginBottom: '1rem' }}>
          VaniGuard uses no third-party tracking cookies. Anonymous usage
          analytics (page views, error rates) may be collected by the hosting
          provider (Streamlit Cloud) subject to their own privacy policy.
        </p>
        <h2>4. Data Retention</h2>
        <p style={{ color: 'var(--text-muted)', marginBottom: '1rem' }}>
          Detection history is retained until you choose to clear it from the
          History page. You may delete all records at any time.
        </p>
        <h2>5. Contact</h2>
        <p style={{ color: 'var(--text-muted)' }}>
          For privacy questions, contact us at{' '}
          <a href="mailto:privacy@vaniguard.ai" style={{ color: 'var(--primary)' }}>
            privacy@vaniguard.ai
          </a>.
        </p>
      </div>
    </div>
  );
}
