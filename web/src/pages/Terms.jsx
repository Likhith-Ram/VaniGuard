import useDocTitle from '../hooks/useDocTitle';

export default function Terms() {
  useDocTitle('Terms & Conditions');

  return (
    <div style={{ maxWidth: '760px', margin: '0 auto' }}>
      <h1>Terms &amp; Conditions</h1>
      <p style={{ color: 'var(--text-muted)', marginBottom: '2rem' }}>
        Last updated: 27 September 2026
      </p>

      <div className="card">
        <h2>1. Acceptance of Terms</h2>
        <p style={{ color: 'var(--text-muted)', marginBottom: '1rem' }}>
          By using VaniGuard, you agree to these Terms &amp; Conditions. If you
          disagree with any part, please discontinue use immediately.
        </p>
        <h2>2. Use of the Service</h2>
        <p style={{ color: 'var(--text-muted)', marginBottom: '1rem' }}>
          VaniGuard is provided as a research and demonstration tool for
          detecting AI-generated voices. You agree to use it lawfully and not
          to upload audio belonging to third parties without authorization.
        </p>
        <h2>3. No Warranty</h2>
        <p style={{ color: 'var(--text-muted)', marginBottom: '1rem' }}>
          VaniGuard is provided &ldquo;as is&rdquo; without warranty of any kind.
          Detection results are probabilistic and should not be used as the
          sole basis for legal, medical, or security decisions.
        </p>
        <h2>4. Limitation of Liability</h2>
        <p style={{ color: 'var(--text-muted)', marginBottom: '1rem' }}>
          To the fullest extent permitted by law, the VaniGuard team shall not
          be liable for any indirect, incidental, or consequential damages
          arising from your use of the service.
        </p>
        <h2>5. Intellectual Property</h2>
        <p style={{ color: 'var(--text-muted)', marginBottom: '1rem' }}>
          The VaniGuard source code is MIT-licensed. The trained model weights
          (vaniguard.onnx) are proprietary. You may not redistribute the model
          without explicit permission.
        </p>
        <h2>6. Changes to Terms</h2>
        <p style={{ color: 'var(--text-muted)' }}>
          We reserve the right to update these terms at any time. Continued use
          of VaniGuard after changes constitutes acceptance.
        </p>
      </div>
    </div>
  );
}
