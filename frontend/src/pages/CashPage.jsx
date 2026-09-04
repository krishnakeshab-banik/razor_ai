import React from 'react';
import { useApp } from '../AppContext';
import { formatRupees } from '../lib/format';
import { api } from '../lib/api';
import { useLanguage } from '../i18n/LanguageContext';

export default function CashPage() {
  const { cash, closeReport, reconciliationRun, handleWhatIf, whatIfResult } = useApp();
  const { t } = useLanguage();
  const [why, setWhy] = React.useState(null);
  const [whyLoading, setWhyLoading] = React.useState(false);

  const loadWhy = async () => {
    setWhyLoading(true);
    try {
      setWhy(await api.cashWhy());
    } catch {
      setWhy({ summary: 'Could not calculate the cash gap.' });
    } finally {
      setWhyLoading(false);
    }
  };
  if (!reconciliationRun) {
    return (
      <div className="db-page">
        <div className="db-card" data-tour="cash-position">
          <p className="db-table-empty">Reconcile a batch to see cash position.</p>
          <p className="text-dim" data-tour="cash-why">Why is my cash different? is available after a batch is reconciled.</p>
        </div>
      </div>
    );
  }

  const maxInflow = Math.max(1, ...(cash?.forecast || []).map((day) => day.expected_inflow_rupees));
  const projected = cash?.projected_cash_rupees ?? ((cash?.available_rupees || 0) + (cash?.in_transit_rupees || 0));

  return (
    <div className="db-page">
      <div>
        <h2 className="db-page-title">{t('pages.cashTitle')}</h2>
        <p className="db-page-sub">{t('pages.cashSub')}</p>
      </div>
      <div data-tour="cash-position">
      <div className="db-cash-hero">
        <div>
          <span>How much money do I have?</span>
          <strong>{formatRupees(cash?.available_rupees)}</strong>
          <small>Available now (settled, minus withdrawals)</small>
        </div>
        <div>
          <span>What will it look like?</span>
          <strong>{formatRupees(projected)}</strong>
          <small>Available + in-transit</small>
        </div>
      </div>
      <div className="db-reports-summary-row">
        <div className="db-report-highlight-card db-report-highlight-green">
          <span className="db-report-kicker">Available</span>
          <strong>{formatRupees(cash?.available_rupees)}</strong>
          <small>Matched and past settled_at</small>
        </div>
        <div className="db-report-highlight-card db-report-highlight-blue">
          <span className="db-report-kicker">Pending settlement</span>
          <strong>{formatRupees(cash?.expected_incoming_rupees ?? cash?.in_transit_rupees)}</strong>
          <small>In transit</small>
        </div>
        <div className="db-report-highlight-card db-report-highlight-amber">
          <span className="db-report-kicker">At risk / unresolved</span>
          <strong>{formatRupees(cash?.unresolved_amount_rupees ?? cash?.blocked_rupees)}</strong>
          <small>Open exceptions</small>
        </div>
        <div className="db-report-highlight-card db-report-highlight-violet">
          <span className="db-report-kicker">Expected outgoing</span>
          <strong>{formatRupees(cash?.expected_outgoing_rupees)}</strong>
          <small>Pending payouts (none unless recorded)</small>
        </div>
      </div>
      </div>
      <div className="db-page-heading">
        <button className="db-topbar-cta" type="button" data-tour="cash-why" onClick={loadWhy} disabled={whyLoading}>
          {whyLoading ? 'Tracing…' : 'Why is my cash different?'}
        </button>
      </div>
      {why && (
        <div className="db-card">
          <h3 className="db-card-title">Expected vs actual cash</h3>
          <div className="db-waterfall">
            <div className="db-waterfall-row"><span>Expected (GMV)</span><strong>{formatRupees(why.expected_rupees)}</strong></div>
            <div className="db-waterfall-row"><span>Actual (available)</span><strong>{formatRupees(why.actual_rupees)}</strong></div>
            <div className="db-waterfall-row"><span>Difference</span><strong>{formatRupees(why.difference_rupees)}</strong></div>
            {(why.breakdown || []).map((item) => (
              <div className="db-waterfall-row" key={item.id}><span>{item.label}</span><strong>{formatRupees(item.rupees)}</strong></div>
            ))}
            <div className="db-waterfall-row"><span>Unexplained</span><strong>{formatRupees(why.unexplained_rupees)}</strong></div>
          </div>
          <p>{why.summary}</p>
          <p className="text-dim">{why.formula}</p>
        </div>
      )}
      {cash?.withdrawn_rupees > 0 && (
        <p className="db-card-sub">Already withdrawn: {formatRupees(cash.withdrawn_rupees)}. Previously withdrawn funds are excluded from available cash.</p>
      )}

      {!!cash?.alerts?.length && (
        <div className="db-card">
          <h3 className="db-card-title">Cash-flow risk alerts</h3>
          {cash.alerts.map((alert) => (
            <div className="db-alert-row" key={alert.code}>
              <strong>{alert.message}</strong>
              <p>{alert.why}</p>
            </div>
          ))}
        </div>
      )}

      <div className="db-card">
        <h3 className="db-card-title">7-day incoming settlements</h3>
        <div className="db-forecast-list">
          {(cash?.forecast || []).map((day) => (
            <div className="db-forecast-row" key={day.date}>
              <span className="db-forecast-label">{day.label}</span>
              <div className="db-forecast-bar-track">
                <div className="db-forecast-bar" style={{ width: `${(day.expected_inflow_rupees / maxInflow) * 100}%` }} />
              </div>
              <strong>{formatRupees(day.expected_inflow_rupees)}</strong>
              <span className="text-dim">{day.payments_due} due · {day.exceptions_due} blocked</span>
            </div>
          ))}
        </div>
      </div>

      <div className="db-card">
        <h3 className="db-card-title">What-if analysis</h3>
        <p className="db-card-sub">Recalculates cash deterministically. The LLM does not invent these numbers.</p>
        <div className="db-whatif-actions">
          <button className="db-filter-btn" type="button" onClick={() => handleWhatIf({ delay_settlement_rupees: 200000, refund_increase_pct: 0, drop_unresolved: false, extra_payout_rupees: 0 })}>Delay ₹2L settlement</button>
          <button className="db-filter-btn" type="button" onClick={() => handleWhatIf({ delay_settlement_rupees: 0, refund_increase_pct: 20, drop_unresolved: false, extra_payout_rupees: 0 })}>Refunds +20%</button>
          <button className="db-filter-btn" type="button" onClick={() => handleWhatIf({ delay_settlement_rupees: 0, refund_increase_pct: 0, drop_unresolved: true, extra_payout_rupees: 0 })}>Unresolved not received</button>
        </div>
        {whatIfResult && (
          <div className="db-waterfall">
            <p>{whatIfResult.explanation}</p>
            <div className="db-waterfall-row"><span>Projected cash</span><strong>{formatRupees(whatIfResult.projected_cash_rupees)}</strong></div>
            <div className="db-waterfall-row"><span>Change vs base</span><strong>{formatRupees(whatIfResult.delta_vs_base_rupees)}</strong></div>
          </div>
        )}
      </div>

      {closeReport && (
        <div className="db-card">
          <h3 className="db-card-title">Last close — exceptions still open</h3>
          <p className="db-card-sub">{closeReport.remaining_exceptions.length} honest remainder after auto-resolve.</p>
        </div>
      )}
    </div>
  );
}
