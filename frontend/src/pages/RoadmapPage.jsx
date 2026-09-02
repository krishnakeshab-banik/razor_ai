export default function RoadmapPage() {
  return (
    <div>
      <div className="roadmap-hero">
        <div className="container">
          <span className="badge" style={{ backgroundColor: '#fdf2f8', color: '#db2777', textTransform: 'none', borderRadius: 4, fontSize: 11, fontWeight: 500 }}>
            Built for Razorpay-shaped ops
          </span>
          <h1 className="section-title">From spreadsheet close to a finance controller</h1>
          <p className="section-subtitle">
            Phase 1 is live: measured match rate, auto-resolution, GST lines, multi-source breaks and a 7-day cash forecast on synthetic batches.
          </p>
        </div>
      </div>
      <div className="roadmap-phases-section">
        <div className="container">
          <div className="phases-intro">
            <h2>Development phases</h2>
            <p>Ship the verification loop first. Integrations come after the books already close on synthetic data.</p>
          </div>
          <div className="roadmap-timeline-wrapper">
            <div className="phase-wide-card">
              <div className="phase-wide-icon-circle">Live</div>
              <div className="phase-card-info">
                <div className="phase-header-row">
                  <span style={{ fontSize: 12, fontWeight: 700, color: '#005ce6' }}>Phase 1</span>
                  <span className="badge-status-live">LIVE IN THIS DEMO</span>
                </div>
                <h3>Finance controller on a 50+ batch</h3>
                <p>Deterministic matching, GST 18% on fee, exception auto-fix, honest remainder, cash position, settlement Q&A grounded in payment IDs.</p>
                <ul className="roadmap-checklist" style={{ listStyle: 'none', display: 'flex', gap: 20, marginTop: 12, flexWrap: 'wrap' }}>
                  <li>✓ Reconciliation</li>
                  <li>✓ Close the books</li>
                  <li>✓ Cash forecast</li>
                  <li>✓ Tax-line matcher</li>
                </ul>
              </div>
            </div>
            <div className="phases-subgrid">
              <div className="phase-grid-card">
                <h4><span style={{ color: '#005ce6' }}>Phase 2</span><span>Next</span></h4>
                <h3>Live Razorpay + bank hooks</h3>
                <p>Replace the synthetic batch with Payments API, settlements and a current-account statement so the same engine runs on production files.</p>
              </div>
              <div className="phase-grid-card">
                <h4><span style={{ color: '#005ce6' }}>Phase 3</span><span>Later</span></h4>
                <h3>Route-level fee cards</h3>
                <p>UPI vs card vs netbanking fee schedules, MDR promotions and instant settlements instead of a flat 2% demo tariff.</p>
              </div>
              <div className="phase-grid-card">
                <h4><span style={{ color: '#005ce6' }}>Phase 4</span><span>After that</span></h4>
                <h3>Autonomous chase</h3>
                <p>Open tickets for missing UTRs without inventing credits — the same honesty rule this demo already enforces.</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
