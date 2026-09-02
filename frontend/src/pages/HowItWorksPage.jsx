export default function HowItWorksPage() {
  return (
    <section className="how-it-works-section">
      <div className="container">
        <div className="section-header text-center">
          <span className="badge badge-blue" style={{ borderRadius: 20, fontSize: 10 }}>The close loop</span>
          <h2 className="section-title">Ingest. Match. Resolve. Forecast.</h2>
          <p className="section-subtitle">
            Verification is the bottleneck, not generation. Razor-AI keeps arithmetic deterministic and only uses Gemini for open-ended settlement questions.
          </p>
        </div>
        <div className="pipeline-grid">
          <div className="pipeline-card">
            <div className="pipeline-icon-box icon-box-blue">1</div>
            <h3>Ingest three ledgers</h3>
            <p>Payments (GMV, fee, GST, refunds), settlements (UTR + credited amount) and the implied bank credit are normalised from CSV or a generated 100-row Razorpay batch.</p>
            <div className="code-terminal">
              <div className="terminal-header"><span /><span /><span /></div>
              <div className="terminal-body">
                <div className="log-line text-dim">INGEST pay_8f21 captured ₹4,528.17</div>
                <div className="log-line text-dim">INGEST setl_1102 T+2 UTR</div>
                <div className="log-line text-dim">INGEST GST 18% of fee</div>
              </div>
            </div>
          </div>
          <div className="pipeline-card">
            <div className="pipeline-icon-box icon-box-mediumblue">2</div>
            <h3>Rule engine, not a model</h3>
            <p>expected = amount − fee − tax − refund. Fee must be 2% of GMV. GST must be 18% of fee. Settlement later than 7 days is a timing break. Duplicates are dropped on close.</p>
            <div className="table-preview">
              <table>
                <tbody>
                  <tr><td>pay_8f21</td><td style={{ color: '#2563eb', textAlign: 'right' }}>Three-way match</td></tr>
                  <tr><td>pay_9c40</td><td style={{ color: '#dc2626', textAlign: 'right' }}>GST line mismatch</td></tr>
                  <tr><td>pay_1aa2</td><td style={{ color: '#b45309', textAlign: 'right' }}>Missing settlement</td></tr>
                </tbody>
              </table>
            </div>
          </div>
          <div className="pipeline-card">
            <div className="pipeline-icon-box icon-box-purple">3</div>
            <h3>Close, then ask</h3>
            <p>Auto-fix fee/GST/refund/timing. Escalate missing UTRs. Then ask Gemini only against the retrieved rows — never against the whole ledger.</p>
            <div className="insight-box">
              <div className="insight-header"><strong>Honest remainder</strong></div>
              <p className="insight-text">
                “pay_1aa2 has no settlement_id. I will not invent a bank credit. Chase Razorpay for the UTR.”
              </p>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
