export default function PoliciesPage() {
  return (
    <div style={{ padding: '2.5rem' }}>
      <div style={{ marginBottom: "2rem", display: "flex", alignItems: "flex-start", justifyContent: "space-between" }}>
        <div>
          <h1 style={{ fontSize: '1.25rem', marginBottom: '0.25rem' }}>Policies</h1>
          <p style={{ fontSize: '0.875rem', color: 'var(--text-muted)' }}>
            Manage organizational rules for AI capabilities.
          </p>
        </div>
      </div>
      
      <div style={{ display: "grid", gap: "1.5rem" }}>
        <div className="card">
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <div>
              <p style={{ fontSize: "0.875rem", fontWeight: 600, color: "var(--text-primary)" }}>Detection & Analysis</p>
              <p style={{ fontSize: "0.8125rem", color: "var(--text-secondary)", marginTop: "0.25rem" }}>
                FixFlow automatically analyzes all detected incidents.
              </p>
            </div>
            <span style={{ fontSize: "0.75rem", background: "var(--bg-surface-2)", border: "1px solid var(--border)", padding: "0.25rem 0.75rem", borderRadius: "9999px", color: "var(--text-muted)" }}>Enforced by default</span>
          </div>
        </div>

        <div className="card">
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <div>
              <p style={{ fontSize: "0.875rem", fontWeight: 600, color: "var(--text-primary)" }}>Autonomous Repair</p>
              <p style={{ fontSize: "0.8125rem", color: "var(--text-secondary)", marginTop: "0.25rem" }}>
                Allow AI to generate and propose patches for known failure types.
              </p>
            </div>
            <label style={{ display: "flex", alignItems: "center", cursor: "pointer", background: "var(--accent)", width: "36px", height: "20px", borderRadius: "10px", position: "relative" }}>
              <div style={{ position: "absolute", right: "2px", width: "16px", height: "16px", background: "#fff", borderRadius: "50%" }} />
            </label>
          </div>
        </div>

        <div className="card">
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <div>
              <p style={{ fontSize: "0.875rem", fontWeight: 600, color: "var(--text-primary)" }}>Verification Tests</p>
              <p style={{ fontSize: "0.8125rem", color: "var(--text-secondary)", marginTop: "0.25rem" }}>
                Require patches to pass static analysis and unit tests before PR creation.
              </p>
            </div>
            <label style={{ display: "flex", alignItems: "center", cursor: "pointer", background: "var(--accent)", width: "36px", height: "20px", borderRadius: "10px", position: "relative" }}>
              <div style={{ position: "absolute", right: "2px", width: "16px", height: "16px", background: "#fff", borderRadius: "50%" }} />
            </label>
          </div>
        </div>
      </div>
    </div>
  );
}
