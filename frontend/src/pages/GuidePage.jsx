import React, { useState } from 'react';
import { useApp } from '../AppContext';
import { useTour } from '../tour/TourContext';
import { JOURNEY } from '../tour/steps';

const MANUAL = [
  { id: 'marketplace', title: 'Shop', body: 'Northwind Goods. Add a product, check out, optionally plant a break. That is how money enters the controller.' },
  { id: 'payments', title: 'Payments', body: 'Every capture in the batch. Search the payment_id from checkout. Exception rows open the queue.' },
  { id: 'gst', title: 'Fee & GST', body: 'Fee is ~2% of GMV. GST is 18% of that fee. Mismatched tax lines jump to Exceptions.' },
  { id: 'cash', title: 'Settlement / Cash', body: 'Captured is not settled. Available, T+2 in-transit, and amount blocked by exceptions.' },
  { id: 'reconciliation', title: 'Reconciliation', body: 'Generate or upload a batch, then run the engine. Matching is deterministic — Gemini is only for Q&A.' },
  { id: 'exceptions', title: 'Exceptions', body: 'Flagged payments. Open one, explain the difference, investigate, then apply a fix or escalate.' },
  { id: 'home', title: 'Dashboard', body: 'Match rate, work queue, cash strip, and Settlement Q&A for a day or this batch.' },
  { id: 'withdraw', title: 'Withdraw', body: 'Eligible cash only. Confirming writes a synthetic withdrawal, not a bank transfer.' },
  { id: 'audit', title: 'Audit logs', body: 'Engine, human, and Gemini actions. Proof that a waive did not invent a UTR.' },
  { id: 'knowledge', title: 'Rules', body: 'Standing human guidance for investigators. Rules never auto-post settlements.' },
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
        <p className="tour-guide-kicker">Live product tour</p>
        <h2 className="db-page-title">How a rupee moves through Razor-AI</h2>
        <p className="db-page-sub">
          Start in the shop, make a purchase, then follow Payment → Fee → Refund → Settlement → Reconciliation → Exception → Investigation → Human resolution on the real screens. The tour highlights live controls. It will not Pay, Refund, Apply fix, or Close books for you.
        </p>
        <div className="tour-guide-ctas">
          <button type="button" className="tour-primary" onClick={() => startTour()}>
            Start from the shop
          </button>
          <button type="button" className="tour-secondary" onClick={() => startTour({ handsOn: true })}>
            Hands-on tour
          </button>
          <button type="button" className="tour-secondary" onClick={() => setManualOpen((open) => !open)}>
            {manualOpen ? 'Hide pages' : 'Open pages yourself'}
          </button>
        </div>
      </div>

      <h3 className="tour-guide-section-title">The close loop</h3>
      <p className="db-page-sub">Click a stage to start the visual guide there. Each popover explains what the screen means and what you should do when something is flagged.</p>
      <ol className="guide-journey">
        {JOURNEY.map((stage, index) => (
          <li key={stage.section}>
            <button type="button" className="guide-journey-card" onClick={() => startTour({ section: stage.section })}>
              <span className="guide-journey-num">{index + 1}</span>
              <h3>{stage.title}</h3>
              <p>{stage.body}</p>
              <span>Start this chapter →</span>
            </button>
          </li>
        ))}
      </ol>

      {manualOpen && (
        <>
          <h3 className="tour-guide-section-title">Open a live page</h3>
          <p className="db-page-sub">Same screens the tour uses. Use these when you already know the loop and just want to jump.</p>
          <div className="db-guide-grid">
            {MANUAL.map((step) => (
              <button key={step.id} type="button" className="db-guide-card" onClick={() => go(step.id)}>
                <h3>{step.title}</h3>
                <p>{step.body}</p>
                <span>Open {step.title} →</span>
              </button>
            ))}
          </div>
          <div className="db-card">
            <h3 className="db-card-title">If a payment is flagged</h3>
            <ol className="db-guide-actions">
              <li>Open <strong>Notifications</strong> or <strong>Payments → Exceptions</strong>. Flagged means the books cannot prove the credit — the customer charge usually already succeeded.</li>
              <li>Read the <strong>mismatch type</strong>. Missing settlement = no UTR (human chase). Fee / GST = arithmetic you can often apply. Unaccounted refund = refund not in the batch.</li>
              <li>Click the payment → <strong>Explain this difference</strong> (GMV → fee → GST → refund → credited) → <strong>Investigate exception</strong>.</li>
              <li><strong>Apply suggested fix</strong> only when the card says it is auto-fixable. Otherwise <strong>Escalate</strong>. Do not waive a missing bank credit without a note.</li>
            </ol>
          </div>
        </>
      )}
    </div>
  );
}
