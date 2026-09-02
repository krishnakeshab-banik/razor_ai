import { useApp } from '../AppContext';
import { formatPaise, matchPercent } from '../lib/format';

export default function LandingPage() {
  const { setActiveTab, setMerchantView, metrics, reconciliationRun, isConnected, handleLoadBatch, batchLoaded, handleRunReconciliation } = useApp();

  return (
    <div>
      <section className="hero-section">
        <div className="container hero-container">
          <div className="hero-text-content">
            <p className="hero-kicker">AI Finance Controller · Razorpay settlements</p>
            <h1 className="hero-title">Close the books. Know the cash.</h1>
            <p className="hero-subtitle">
              Razorpay still leaves finance teams matching payments, fees, GST and T+2 settlements by hand.
              Razor-AI runs that loop on a 50+ record batch, reports the match rate, auto-fixes what is arithmetic,
              and leaves an honest list of exceptions it will not invent a bank credit for.
            </p>
            <div className="hero-actions">
              <button
                className="btn btn-primary btn-lg"
                onClick={() => {
                  setMerchantView('store');
                  setActiveTab('merchant-checkout');
                }}
              >
                Try a live checkout
              </button>
              <button className="btn btn-secondary btn-lg" onClick={() => setActiveTab('dashboard')}>
                Open the controller
              </button>
            </div>
          </div>

          <div className="hero-mockup-wrapper">
            <div className="mockup-frame">
              <div className="mockup-header">
                <div className="mockup-dots"><span /><span /><span /></div>
                <div className="mockup-title">Books close · Razorpay INR settlements</div>
                <div className="mockup-status-indicator">
                  <span className={`status-dot ${isConnected ? 'status-online' : 'status-offline'}`} />
                  <span className="status-text" style={{ fontSize: 10, color: '#64748b' }}>{isConnected ? 'Engine live' : 'Engine offline'}</span>
                </div>
              </div>
              <div className="mockup-body">
                <div className="preview-dashboard-layout">
                  <div className="preview-sidebar">
                    <span className="preview-sidebar-icon active">Dash</span>
                    <span className="preview-sidebar-icon">Pay</span>
                    <span className="preview-sidebar-icon">Exc</span>
                    <span className="preview-sidebar-icon">Cash</span>
                  </div>
                  <div className="preview-main-content">
                    <div className="preview-navbar-row">
                      <span className="preview-navbar-title">Cash position after T+2 settlement</span>
                      <div className="preview-navbar-filters">
                        <span className="preview-filter-badge">INR</span>
                        <span className="preview-filter-badge" style={{ backgroundColor: '#eff6ff', color: '#1e40af', border: '1px solid #bfdbfe' }}>GST 18%</span>
                      </div>
                    </div>
                    <div className="preview-stats-grid">
                      <div className="preview-stat-card">
                        <span className="preview-stat-label">Match rate</span>
                        <div className="preview-stat-val">{reconciliationRun ? matchPercent(metrics) : '—'}</div>
                        <span className="preview-stat-trend text-success">measured vs answer key</span>
                      </div>
                      <div className="preview-stat-card">
                        <span className="preview-stat-label">Records</span>
                        <div className="preview-stat-val">{metrics?.total_records || '100+'}</div>
                        <span className="preview-stat-trend text-success">batch, not a cherry-pick</span>
                      </div>
                      <div className="preview-stat-card">
                        <span className="preview-stat-label">Open exceptions</span>
                        <div className="preview-stat-val" style={{ color: '#005ce6' }}>{reconciliationRun ? (metrics?.unresolved_exceptions ?? metrics?.exceptions) : '—'}</div>
                        <span className="preview-stat-trend" style={{ color: '#0284c7' }}>honest remainder</span>
                      </div>
                      <div className="preview-stat-card">
                        <span className="preview-stat-label">Amount matched</span>
                        <div className="preview-stat-val">{reconciliationRun && metrics ? formatPaise(metrics.amount_reconciled) : '₹—'}</div>
                        <span className="preview-stat-trend" style={{ color: '#64748b' }}>paise-accurate</span>
                      </div>
                    </div>
                    <div className="preview-middle-row">
                      <div className="preview-graph-card">
                        <span className="preview-graph-title">7-day settlement inflow vs blocked exceptions</span>
                        <div className="preview-chart-canvas">
                          <svg className="preview-chart-svg" viewBox="0 0 400 120" preserveAspectRatio="none">
                            <path d="M0,110 C50,110 50,20 100,20 C150,20 150,105 200,105 C250,105 250,40 300,40 C350,40 350,110 400,110 L400,120 L0,120 Z" fill="rgba(0, 92, 230, 0.08)" />
                            <path d="M0,110 C50,110 50,20 100,20 C150,20 150,105 200,105 C250,105 250,40 300,40 C350,40 350,110 400,110" fill="none" stroke="#005ce6" strokeWidth="2" />
                          </svg>
                        </div>
                      </div>
                      <div className="preview-insights-card">
                        <span className="preview-insights-title">What the agent will not fake</span>
                        <div className="preview-insights-body">
                          <div className="preview-insights-header">Missing settlement</div>
                          <p className="preview-insights-text">
                            Fee, GST and refund arithmetic can be auto-corrected. A missing UTR cannot.
                            Those stay on the exception list until a human chases Razorpay or the bank.
                          </p>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
                {!reconciliationRun && (
                  <div className="mockup-placeholder-cta">
                    <button className="btn btn-primary btn-lg" onClick={handleLoadBatch} disabled={!isConnected || batchLoaded} type="button">
                      {batchLoaded ? 'Batch loaded' : 'Load demo batch'}
                    </button>
                    {batchLoaded && (
                      <button className="btn btn-primary btn-lg" onClick={() => handleRunReconciliation({ force: true })} type="button" style={{ marginLeft: 10 }}>
                        Run reconciliation
                      </button>
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="comparison-section">
        <div className="container">
          <div className="comparison-grid">
            <div className="comparison-card without-card">
              <div className="card-header">
                <h3 style={{ color: '#dc2626' }}>How finance teams close Razorpay today</h3>
              </div>
              <ul className="comparison-list">
                <li>
                  <strong>CSV vs settlement file vs bank</strong>
                  <span>Payments, fees, GST and UTRs live in three exports that get VLOOKUP’d at month end.</span>
                </li>
                <li>
                  <strong>T+2 cash is a guess</strong>
                  <span>Captured is not settled. Nobody has a 7-day view of what will actually hit the current account.</span>
                </li>
                <li>
                  <strong>One pretty match proves nothing</strong>
                  <span>A single cleaned row is not a close. Throughput, measured accuracy and leftovers are the bar.</span>
                </li>
              </ul>
            </div>
            <div className="comparison-card with-card">
              <div className="card-header">
                <h3 style={{ color: '#005ce6' }}>With Razor-AI</h3>
              </div>
              <ul className="comparison-list">
                <li>
                  <strong>One loop, one match rate</strong>
                  <span>Ingest a 50+ batch, match in paise, auto-fix fee/GST/refund math, report what remains.</span>
                </li>
                <li>
                  <strong>Cash position, not just exceptions</strong>
                  <span>Available, in-transit and blocked cash, plus a 7-day settlement forecast.</span>
                </li>
                <li>
                  <strong>Grounded settlement Q&A</strong>
                  <span>Gemini may only speak from the records it retrieved. Payment IDs are clickable receipts.</span>
                </li>
              </ul>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
