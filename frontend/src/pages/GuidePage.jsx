import React, { useState } from 'react';
import { useApp } from '../AppContext';
import { useTour } from '../tour/TourContext';

const STEPS = [
  { id: 'home', title: 'Dashboard', body: 'Use this page to see overall finance status, unresolved amount, reconciliation performance and cash position.' },
  { id: 'payments', title: 'Payments', body: 'View payments. Use the date filter to find a period. Click an exception row to inspect it in Exceptions.' },
  { id: 'exceptions', title: 'Exceptions', body: 'Find transactions that could not be reconciled automatically. Open one and click Explain this difference.' },
  { id: 'cash', title: 'Cash', body: 'See current available cash, pending settlements, unresolved amount, and projected cash.' },
  { id: 'gst', title: 'GST', body: 'Inspect GST collected vs expected (GST is on the processing fee) and jump into tax-line exceptions.' },
  { id: 'audit', title: 'Audit logs', body: 'See every important rule-engine, human, and Gemini action. Filters apply to the stored audit trail.' },
  { id: 'knowledge', title: 'Rules', body: 'Standing human guidance for investigators. Rules never auto-fix books or invent a settlement.' },
  { id: 'marketplace', title: 'Marketplace', body: 'Demo store checkout lands in the same reconciliation batch. Flagged payments create notifications in the controller.' },
  { id: 'withdraw', title: 'Withdraw', body: 'Review available funds, previously withdrawn amounts, and how much you will actually receive before confirming.' },
  { id: 'reconciliation', title: 'Reconciliation', body: 'Generate or upload a batch, then run the engine. Matching is deterministic — Gemini is only for Q&A.' },
];

export default function GuidePage() {
  const { setDashPage, setActiveTab, setMerchantView } = useApp();
  const { startTour } = useTour();
  const [manualOpen, setManualOpen] = useState(true);

  const go = (id) => {
    if (id === 'marketplace') {
      setMerchantView('store');
      setActiveTab('merchant-checkout');
      return;
    }
    setDashPage(id);
  };

  return (
    <div className="db-page">
      <div className="tour-guide-hero">
        <p className="tour-guide-kicker">Manual guide</p>
        <h2 className="db-page-title">AI Finance Controller — Guided Tour</h2>
        <p className="db-page-sub">Explore the Finance Controller by following a guided walkthrough of the actual application.</p>
        <div className="tour-guide-ctas">
          <button type="button" className="tour-primary" onClick={() => startTour()}>
            Start Guided Tour
          </button>
          <button type="button" className="tour-secondary" onClick={() => startTour({ handsOn: true })}>
            Hands-on tour
          </button>
          <button type="button" className="tour-secondary" onClick={() => setManualOpen((open) => !open)}>
            {manualOpen ? 'Hide manual sections' : 'Explore Manually'}
          </button>
        </div>
      </div>

      {manualOpen && (
        <>
          <h3 className="tour-guide-section-title">Explore manually</h3>
          <p className="db-page-sub">Click a section to open that page. These are the same live screens the tour uses.</p>
          <div className="db-guide-grid">
            {STEPS.map((step) => (
              <button key={step.id} type="button" className="db-guide-card" onClick={() => go(step.id)}>
                <h3>{step.title}</h3>
                <p>{step.body}</p>
                <span>Open {step.title} →</span>
              </button>
            ))}
          </div>
          <div className="db-card">
            <h3 className="db-card-title">Buttons that actually exist</h3>
            <ul className="db-guide-actions">
              <li><strong>Generate Demo Dataset</strong> — Reconciliation page. Creates a batch and runs the real engine.</li>
              <li><strong>Explain this difference</strong> — Exception detail. Waterfall of GMV → fee → GST → refunds → credited.</li>
              <li><strong>Investigate exception</strong> — Deterministic scan. No invented evidence.</li>
              <li><strong>Apply suggested fix</strong> — Only when the type is auto-fixable.</li>
              <li><strong>Close books</strong> — Top bar. Auto-resolves arithmetic; missing UTRs stay on the list.</li>
              <li><strong>Confirm withdrawal</strong> — Withdraw page. Records a synthetic withdrawal, not a bank transfer.</li>
            </ul>
          </div>
        </>
      )}
    </div>
  );
}
