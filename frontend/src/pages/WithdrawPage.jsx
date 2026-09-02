import React, { useEffect, useState } from 'react';
import DateRangeFilter, { EMPTY_DATE_FILTER } from '../components/DateRangeFilter';
import { useApp } from '../AppContext';
import { formatRupees, formatTimestamp } from '../lib/format';

export default function WithdrawPage() {
  const {
    reconciliationRun, withdrawAvailability, withdrawHistory, lastWithdrawal,
    fetchWithdrawals, handlePreviewWithdraw, handleConfirmWithdraw,
    withdrawPreview, withdrawing,
  } = useApp();
  const [asOf, setAsOf] = useState('');
  const [amount, setAmount] = useState('');
  const [historyFilter, setHistoryFilter] = useState(EMPTY_DATE_FILTER);
  const [historySearch, setHistorySearch] = useState('');
  const [confirmOpen, setConfirmOpen] = useState(false);

  useEffect(() => {
    if (reconciliationRun) fetchWithdrawals(asOf || undefined, historyFilter, historySearch);
  }, [reconciliationRun, asOf, historyFilter, historySearch, fetchWithdrawals]);

  useEffect(() => {
    if (!reconciliationRun) return undefined;
    const handle = window.setTimeout(() => {
      handlePreviewWithdraw(Number(amount) || 0, asOf || undefined);
    }, 250);
    return () => window.clearTimeout(handle);
  }, [amount, asOf, reconciliationRun, handlePreviewWithdraw]);

  if (!reconciliationRun) {
    return (
      <div className="db-page">
        <div className="db-card" data-tour="withdraw-available">
          <p className="db-table-empty">Reconcile a batch before withdrawing.</p>
          <p className="text-dim" data-tour="withdraw-date">Date filter, amount, analysis and confirm appear after a batch is loaded.</p>
          <span data-tour="withdraw-amount" />
          <span data-tour="withdraw-analysis" />
          <span data-tour="withdraw-confirm" />
        </div>
      </div>
    );
  }

  const avail = withdrawAvailability || {};
  const preview = withdrawPreview || {};
  const canConfirm = preview.can_withdraw && Number(amount) > 0;

  return (
    <div className="db-page">
      <div className="bank-page-head">
        <div>
          <p className="bank-kicker">Payout account</p>
          <h2 className="db-page-title">Withdraw</h2>
          <p className="db-page-sub">Synthetic payout ledger · account RAZOR-AI / 000182. Previously withdrawn funds are excluded. No bank transfer is sent.</p>
        </div>
        <div className="bank-account-chip">
          <span>Account status</span>
          <strong>{avail.available_rupees > 0 ? 'Active' : 'No surplus'}</strong>
        </div>
      </div>

      <div className="bank-balance-strip bank-strip-payout" data-tour="withdraw-available">
        <div>
          <span>Available to withdraw</span>
          <strong>{formatRupees(avail.available_rupees)}</strong>
        </div>
        <div>
          <span>Earned to date</span>
          <strong>{formatRupees(avail.total_earned_rupees)}</strong>
        </div>
        <div>
          <span>Already withdrawn</span>
          <strong>{formatRupees(avail.already_withdrawn_rupees)}</strong>
        </div>
        <div>
          <span>Refunds in eligible set</span>
          <strong>{formatRupees(avail.refunds_rupees)}</strong>
        </div>
      </div>
      <p className="bank-footnote">Previously withdrawn funds are excluded from this calculation. Demo / synthetic only.</p>

      <div className="bank-split">
        <div className="db-card bank-transfer" data-tour="withdraw-analysis">
          <h3 className="db-card-title">Initiate transfer</h3>
          <label className="bank-field" data-tour="withdraw-date">
            Eligible through
            <input className="db-exc-search" type="datetime-local" value={asOf} onChange={(event) => setAsOf(event.target.value)} />
          </label>
          <label className="bank-field" data-tour="withdraw-amount">
            Transfer amount (₹)
            <input className="db-exc-search bank-amount-input" type="number" min="0" step="0.01" value={amount} onChange={(event) => setAmount(event.target.value)} placeholder="0.00" />
          </label>
          {avail.available_rupees === 0 && (
            <p className="db-ingest-bad">No additional amount is available for withdrawal for this period.</p>
          )}
          {!!preview.errors?.length && (
            <ul className="db-ingest-bad">{preview.errors.map((item) => <li key={item}>{item}</li>)}</ul>
          )}
          <div className="db-waterfall">
            {(preview.steps || []).map((step) => (
              <div className="db-waterfall-row" key={step.id}>
                <span>{step.label}</span>
                <strong>{formatRupees(step.rupees)}</strong>
              </div>
            ))}
          </div>
          <button className="db-topbar-cta" type="button" data-tour="withdraw-confirm" disabled={!canConfirm || withdrawing} onClick={() => setConfirmOpen(true)}>
            Review confirmation
          </button>
        </div>
        <div className="db-card bank-meta">
          <h3 className="db-card-title">Last payout</h3>
          {lastWithdrawal ? (
            <dl>
              <div><dt>When</dt><dd>{formatTimestamp(lastWithdrawal.created_at)}</dd></div>
              <div><dt>Reference</dt><dd>{lastWithdrawal.withdrawal_id}</dd></div>
              <div><dt>Requested</dt><dd>{formatRupees(lastWithdrawal.requested_rupees)}</dd></div>
              <div><dt>You received</dt><dd>{formatRupees(lastWithdrawal.net_rupees)}</dd></div>
              <div><dt>Status</dt><dd>{lastWithdrawal.status} · {lastWithdrawal.environment}</dd></div>
            </dl>
          ) : (
            <p className="db-table-empty">No withdrawals yet.</p>
          )}
        </div>
      </div>

      {confirmOpen && (
        <div className="db-modal-backdrop">
          <div className="db-modal">
            <h3>Confirm withdrawal</h3>
            <p>Demo / synthetic withdrawal. No money is transferred to a bank.</p>
            <div className="db-waterfall">
              <div className="db-waterfall-row"><span>Requested</span><strong>{formatRupees(preview.requested_rupees)}</strong></div>
              <div className="db-waterfall-row"><span>Fees</span><strong>{formatRupees(preview.fee_rupees)}</strong></div>
              <div className="db-waterfall-row"><span>Tax</span><strong>{formatRupees(preview.tax_rupees)}</strong></div>
              <div className="db-waterfall-row"><span>Refunds / adjustments</span><strong>{formatRupees(preview.refund_adjustment_rupees)}</strong></div>
              <div className="db-waterfall-row"><span>You will receive</span><strong>{formatRupees(preview.net_rupees)}</strong></div>
              <div className="db-waterfall-row"><span>Available after</span><strong>{formatRupees(preview.available_after_rupees)}</strong></div>
            </div>
            <div className="db-whatif-actions">
              <button className="db-filter-btn" type="button" onClick={() => setConfirmOpen(false)}>Cancel</button>
              <button
                className="db-topbar-cta"
                type="button"
                disabled={withdrawing}
                onClick={async () => {
                  const ok = await handleConfirmWithdraw(Number(amount), asOf || undefined);
                  if (ok) {
                    setConfirmOpen(false);
                    setAmount('');
                  }
                }}
              >
                {withdrawing ? 'Recording…' : 'Confirm withdrawal'}
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="db-card bank-statement">
        <div className="bank-table-head">
          <h3 className="db-card-title">Payout statement</h3>
          <span>{withdrawHistory.length} entries</span>
        </div>
        <DateRangeFilter value={historyFilter} onChange={setHistoryFilter} />
        <input className="db-exc-search" value={historySearch} onChange={(event) => setHistorySearch(event.target.value)} placeholder="Search withdrawal ID…" />
        <table className="db-table bank-ledger">
          <thead>
            <tr>
              <th>Reference</th>
              <th>Value date</th>
              <th>Requested</th>
              <th>Fees</th>
              <th>Tax</th>
              <th>Credited</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {withdrawHistory.length ? withdrawHistory.map((row) => (
              <tr key={row.withdrawal_id}>
                <td className="db-exc-id">{row.withdrawal_id}</td>
                <td>{formatTimestamp(row.created_at)}</td>
                <td>{formatRupees(row.requested_rupees)}</td>
                <td>{formatRupees(row.fee_rupees)}</td>
                <td>{formatRupees(row.tax_rupees)}</td>
                <td>{formatRupees(row.net_rupees)}</td>
                <td><span className="db-status-badge db-status-reconciled">{row.status}</span></td>
              </tr>
            )) : (
              <tr><td colSpan="7" className="db-table-empty">No withdrawals yet.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
