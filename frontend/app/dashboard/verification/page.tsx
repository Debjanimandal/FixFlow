export default function VerificationPage() {
  return (
    <div style={{ padding: '2.5rem' }}>
      <div style={{ marginBottom: "2rem" }}>
        <h1 style={{ fontSize: '1.25rem', marginBottom: '0.25rem' }}>Verification</h1>
        <p style={{ fontSize: '0.875rem', color: 'var(--text-muted)' }}>
          Static analysis, unit tests, and build verification runs for proposed patches.
        </p>
      </div>
      
      <div className="card" style={{ padding: '5rem 2rem', textAlign: 'center', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '1.25rem' }}>
        <div style={{ width: "48px", height: "48px", borderRadius: "var(--radius-lg)", border: "1px solid var(--border)", display: "flex", alignItems: "center", justifyContent: "center", color: "var(--accent)", background: "var(--accent-dim)" }}>
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
            <path d="M9 11l3 3L22 4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
            <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </div>
        <div>
          <p style={{ fontSize: '1rem', fontWeight: 600, color: "var(--text-primary)" }}>No verification runs yet</p>
          <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', marginTop: '0.375rem', maxWidth: "400px", margin: "0.375rem auto 0" }}>
            FixFlow verifies patches before proposing them. Runs will appear here automatically.
          </p>
        </div>
      </div>
    </div>
  );
}
