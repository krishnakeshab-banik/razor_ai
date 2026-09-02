import React, { useState } from 'react';
import { api } from '../lib/api';
import { useApp } from '../AppContext';
import { formatPaise, formatRupees, titleCaseType } from '../lib/format';

export default function FinanceSearch() {
  const { reconciliationRun, setDashPage, setSelectedExcId, isConnected } = useApp();
  const [query, setQuery] = useState('');
  const [open, setOpen] = useState(false);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  const run = async (event) => {
    event.preventDefault();
    if (!query.trim() || !reconciliationRun) return;
    setLoading(true);
    setOpen(true);
    try {
      setResult(await api.financeSearch(query.trim()));
    } catch (error) {
      setResult({ error: error.message, results: {}, primary: [] });
    } finally {
      setLoading(false);
    }
  };

  const openPayment = (paymentId) => {
    setSelectedExcId(paymentId);
    setDashPage('exceptions');
    setOpen(false);
  };

  const rows = result?.primary || result?.results?.payments || [];

  return (
    <div className="ops-search-wrap">
      <form className="ops-search-form" onSubmit={run}>
        <input
          className="ops-search-input"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Find payment P1024, refunds last week…"
          disabled={!isConnected || !reconciliationRun}
        />
        <button className="db-ghost-btn" type="submit" disabled={!reconciliationRun || loading}>Search</button>
      </form>
      {open && (
        <div className="ops-search-panel">
          <div className="ops-search-head">
            <strong>Finance search</strong>
            <button type="button" className="db-text-link" onClick={() => setOpen(false)}>Close</button>
          </div>
          {loading && <p className="db-table-empty">Searching…</p>}
          {result?.filters && <p className="text-dim">Interpreted as {result.filters.kind}{result.filters.min_rupees ? ` ≥ ₹${result.filters.min_rupees}` : ''}</p>}
          {result?.error && <p className="db-ingest-bad">{result.error}</p>}
          {rows.length ? rows.slice(0, 8).map((row) => (
            <button key={row.payment_id || row.withdrawal_id || JSON.stringify(row)} type="button" className="ops-search-row" onClick={() => row.payment_id && openPayment(row.payment_id)}>
              <span>{row.payment_id || row.withdrawal_id || row.customer_id}</span>
              <strong>{row.amount != null ? formatPaise(row.amount) : formatRupees(row.gmv_rupees || row.requested_rupees)}</strong>
              <small>{titleCaseType(row.mismatch_type || row.reconciliation_status || row.status)}</small>
            </button>
          )) : (!loading && result ? <p className="db-table-empty">No matching records.</p> : null)}
        </div>
      )}
    </div>
  );
}
