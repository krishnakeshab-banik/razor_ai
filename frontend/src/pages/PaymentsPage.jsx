import React, { useEffect } from 'react';
import DateRangeFilter from '../components/DateRangeFilter';
import { useApp } from '../AppContext';
import { formatPaise, formatRupees, formatTimestamp } from '../lib/format';
import { useLanguage } from '../i18n/LanguageContext';

export default function PaymentsPage() {
  const {
    reconciliationRun, paymentFilter, setPaymentFilter, payments, paymentsMeta,
    fetchPayments, paymentSearch, setPaymentSearch, paymentPage, setPaymentPage,
    paymentStatus, setPaymentStatus,
    setSelectedExcId, setDashPage, selectedExcId,
  } = useApp();
  const { t } = useLanguage();

  useEffect(() => {
    if (reconciliationRun) fetchPayments();
  }, [reconciliationRun, paymentFilter, paymentSearch, paymentPage, paymentStatus, fetchPayments]);

  if (!reconciliationRun) {
    return (
      <div className="db-page">
        <div className="db-card" data-tour="payments-heading">
          <p className="db-table-empty" data-tour="payments-table">Reconcile a batch to list payments.</p>
        </div>
      </div>
    );
  }

  const totals = paymentsMeta?.totals || {};

  return (
    <div className="db-page">
      <div className="db-page-heading" data-tour="payments-heading">
        <div>
          <h2 className="db-page-title">{t('pages.paymentsTitle')}</h2>
          <p className="db-page-sub">{t('pages.paymentsSub')}</p>
        </div>
      </div>
      <DateRangeFilter value={paymentFilter} onChange={(next) => { setPaymentPage(1); setPaymentFilter(next); }} dataTour="payments-filter" />
      <div className="db-exc-filters">
        <input
          className="db-exc-search"
          value={paymentSearch}
          onChange={(event) => { setPaymentPage(1); setPaymentSearch(event.target.value); }}
          placeholder="Search payment ID, order ID, or status…"
        />
      </div>
      <div className="db-stats-row">
        <div className="db-stat-card"><span className="db-stat-label">Payments</span><div className="db-stat-value">{totals.count ?? 0}</div></div>
        <div className="db-stat-card"><span className="db-stat-label">GMV</span><div className="db-stat-value">{formatRupees(totals.gmv_rupees)}</div></div>
        <div className="db-stat-card"><span className="db-stat-label">Matched</span><div className="db-stat-value">{totals.matched ?? 0}</div></div>
        <div className="db-stat-card db-stat-card-alert"><span className="db-stat-label">Exceptions</span><div className="db-stat-value db-stat-value-red">{totals.exceptions ?? 0}</div></div>
      </div>
      {paymentsMeta?.filter?.warning && <p className="db-ingest-bad">{paymentsMeta.filter.warning}</p>}
      <div className="ops-console ops-console-payments">
        <aside className="ops-rail" data-tour="payments-rail">
          <div className="ops-rail-group">
            <span>Run results</span>
            {[
              { id: 'all', label: 'All payments', count: totals.count ?? 0 },
              { id: 'matched', label: 'Matched', count: totals.matched ?? 0 },
              { id: 'exception', label: 'Exceptions', count: totals.exceptions ?? 0, danger: true },
            ].map((item) => (
              <button
                key={item.id}
                type="button"
                className={paymentStatus === item.id ? 'active' : ''}
                onClick={() => { setPaymentPage(1); setPaymentStatus(item.id); }}
              >
                {item.label} <em className={item.danger ? 'ops-badge-red' : undefined}>{item.count}</em>
              </button>
            ))}
          </div>
        </aside>
        <div className="db-card ops-table-card" data-tour="payments-table">
        <table className="db-table ops-table mobile-cards">
          <thead>
            <tr>
              <th>ID</th>
              <th>Workflow</th>
              <th>Match status</th>
              <th>Amount</th>
              <th>Input</th>
              <th>Trade date</th>
              <th>Settlement</th>
            </tr>
          </thead>
          <tbody>
            {payments.length ? payments.map((row) => (
              <tr
                key={row.payment_id}
                className={`${row.open_exception ? 'db-exc-row' : ''} ${selectedExcId === row.payment_id ? 'db-row-selected' : ''}`}
                onClick={() => {
                  if (row.open_exception) {
                    setSelectedExcId(row.payment_id);
                    setDashPage('exceptions');
                  }
                }}
              >
                <td data-label="ID"><span className="ops-id-link">{row.payment_id}</span></td>
                <td data-label="Workflow"><span className={`ops-workflow-pill ${row.open_exception ? 'unreviewed' : 'closed'}`}>{row.open_exception ? 'Unreviewed' : 'Closed'}</span></td>
                <td data-label="Match status">{row.reconciliation_status === 'exception' ? (row.mismatch_type === 'partial_settlement' ? 'Partially matched' : 'Unmatched') : 'Matched'}</td>
                <td data-label="Amount">{formatPaise(row.amount)}</td>
                <td data-label="Input">{row.status || 'captured'}</td>
                <td data-label="Trade date" className={row.open_exception ? 'ops-cell-mismatch' : ''}>{formatTimestamp(row.created_at)}</td>
                <td data-label="Settlement">{row.settlement_status}</td>
              </tr>
            )) : (
              <tr><td colSpan="7" className="db-table-empty">{paymentStatus === 'matched' ? 'No matched payments in this filter.' : paymentStatus === 'exception' ? 'No exception payments in this filter.' : 'No payments in this date range.'}</td></tr>
            )}
          </tbody>
        </table>
        <div className="db-pagination-row">
          <button className="db-page-btn" type="button" disabled={paymentPage <= 1} onClick={() => setPaymentPage((page) => page - 1)}>Prev</button>
          <span className="db-pagination-meta">Page {paymentsMeta?.page || 1} / {paymentsMeta?.total_pages || 1}</span>
          <button className="db-page-btn" type="button" disabled={paymentPage >= (paymentsMeta?.total_pages || 1)} onClick={() => setPaymentPage((page) => page + 1)}>Next</button>
        </div>
      </div>
      </div>
    </div>
  );
}
