import React from 'react';
import { formatDelta, formatPaise, formatRupees, titleCaseType } from '../lib/format';

function IssueBadge({ type }) {
  const key = type || 'unclassified_discrepancy';
  return <span className={`db-issue-badge db-issue-${key}`}>{titleCaseType(key)}</span>;
}

function formatCompareValue(row, value) {
  if (row.metric === 'match_rate') {
    return `${Math.round(Number(value || 0) * 100)}%`;
  }
  if (String(row.metric || '').includes('rupees')) {
    return formatRupees(value);
  }
  return value == null ? '—' : String(value);
}

function ToolTable({ columns, rows, empty }) {
  return (
    <div className="db-chat-visual-scroll">
      <table className="db-table ops-table">
        <thead>
          <tr>
            {columns.map((col) => (
              <th key={col.key}>{col.label}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.length ? rows.map((row, index) => (
            <tr key={row.payment_id || row.bucket || row.metric || index}>
              {columns.map((col) => (
                <td key={col.key} className={col.key === 'payment_id' ? 'db-exc-id' : undefined}>
                  {col.render ? col.render(row) : (row[col.key] ?? '—')}
                </td>
              ))}
            </tr>
          )) : (
            <tr>
              <td colSpan={columns.length} className="db-table-empty">{empty}</td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

function TaxTable({ payload }) {
  const rows = Array.isArray(payload?.lines) ? payload.lines : [];
  return (
    <ToolTable
      empty="Every GST line matches 18% of fee."
      columns={[
        { key: 'payment_id', label: 'Payment ID' },
        { key: 'fee_rupees', label: 'Fee', render: (row) => formatRupees(row.fee_rupees) },
        { key: 'expected_gst_rupees', label: 'Expected GST', render: (row) => formatRupees(row.expected_gst_rupees) },
        { key: 'actual_gst_rupees', label: 'Actual GST', render: (row) => formatRupees(row.actual_gst_rupees) },
        {
          key: 'status',
          label: 'Status',
          render: (row) => (
            row.status === 'mismatch'
              ? <IssueBadge type="tax_line_mismatch" />
              : <span className="db-status-badge db-status-reconciled">matched</span>
          ),
        },
      ]}
      rows={rows}
    />
  );
}

function CompareTable({ payload }) {
  const rows = Array.isArray(payload?.changes) ? payload.changes : [];
  return (
    <ToolTable
      empty={payload?.note || 'No financially important changes in this window.'}
      columns={[
        { key: 'title', label: 'Metric' },
        { key: 'current', label: 'Current', render: (row) => formatCompareValue(row, row.current) },
        { key: 'previous', label: 'Previous', render: (row) => formatCompareValue(row, row.previous) },
        { key: 'delta', label: 'Change', render: (row) => formatCompareValue(row, row.delta) },
      ]}
      rows={rows}
    />
  );
}

function RecurringTable({ payload }) {
  const rows = Array.isArray(payload) ? payload : [];
  return (
    <ToolTable
      empty="No recurring discrepancy clusters in this batch."
      columns={[
        { key: 'mismatch_type', label: 'Issue', render: (row) => titleCaseType(row.mismatch_type) },
        { key: 'payment_method', label: 'Method' },
        { key: 'occurrences', label: 'Occurrences' },
        { key: 'affected_rupees', label: 'Affected', render: (row) => formatRupees(row.affected_rupees) },
        {
          key: 'sample_payment_ids',
          label: 'Sample IDs',
          render: (row) => (row.sample_payment_ids || []).join(', ') || '—',
        },
      ]}
      rows={rows}
    />
  );
}

function ExceptionTable({ payload }) {
  const rows = Array.isArray(payload) ? payload : [];
  return (
    <ToolTable
      empty="No high-priority exceptions in this slice."
      columns={[
        { key: 'payment_id', label: 'Payment ID' },
        { key: 'mismatch_type', label: 'Issue', render: (row) => <IssueBadge type={row.mismatch_type} /> },
        { key: 'priority', label: 'Priority' },
        { key: 'amount', label: 'Captured', render: (row) => formatPaise(row.amount) },
        { key: 'delta', label: 'Delta', render: (row) => formatDelta(row.delta) },
      ]}
      rows={rows}
    />
  );
}

function SearchTable({ payload }) {
  const rows = Array.isArray(payload) ? payload : [];
  return (
    <ToolTable
      empty="No matching records."
      columns={[
        { key: 'payment_id', label: 'Payment ID' },
        { key: 'mismatch_type', label: 'Issue', render: (row) => (row.mismatch_type ? titleCaseType(row.mismatch_type) : '—') },
        { key: 'amount', label: 'Captured', render: (row) => formatPaise(row.amount) },
        { key: 'settlement_amount', label: 'Settled', render: (row) => formatPaise(row.settlement_amount) },
        { key: 'reconciliation_status', label: 'Status' },
        { key: 'priority', label: 'Priority', render: (row) => row.priority || '—' },
      ]}
      rows={rows}
    />
  );
}

function CashVisual({ payload }) {
  const cash = payload || {};
  const forecast = Array.isArray(cash.forecast) ? cash.forecast : [];
  const maxInflow = Math.max(1, ...forecast.map((day) => Number(day.expected_inflow_rupees) || 0));
  const projected = cash.projected_cash_rupees ?? ((cash.available_rupees || 0) + (cash.in_transit_rupees || 0));

  return (
    <div className="db-chat-cash-visual">
      <div className="db-reports-summary-row">
        <div className="db-report-highlight-card db-report-highlight-green">
          <span className="db-report-kicker">Available</span>
          <strong>{formatRupees(cash.available_rupees)}</strong>
          <small>Matched and past settled_at</small>
        </div>
        <div className="db-report-highlight-card db-report-highlight-blue">
          <span className="db-report-kicker">In transit</span>
          <strong>{formatRupees(cash.in_transit_rupees)}</strong>
          <small>Pending settlement</small>
        </div>
        <div className="db-report-highlight-card db-report-highlight-amber">
          <span className="db-report-kicker">Blocked</span>
          <strong>{formatRupees(cash.blocked_rupees)}</strong>
          <small>Open exceptions</small>
        </div>
        <div className="db-report-highlight-card db-report-highlight-violet">
          <span className="db-report-kicker">Projected</span>
          <strong>{formatRupees(projected)}</strong>
          <small>Available + in-transit</small>
        </div>
      </div>
      {forecast.length ? (
        <div className="db-forecast-list">
          {forecast.map((day) => (
            <div className="db-forecast-row" key={day.date}>
              <span className="db-forecast-label">{day.label}</span>
              <div className="db-forecast-bar-track">
                <div className="db-forecast-bar" style={{ width: `${(Number(day.expected_inflow_rupees) / maxInflow) * 100}%` }} />
              </div>
              <strong>{formatRupees(day.expected_inflow_rupees)}</strong>
              <span className="text-dim">{day.payments_due} due · {day.exceptions_due} blocked</span>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

export default function ChatToolVisual({ toolUsed, payload }) {
  if (!toolUsed || payload == null) return null;
  if (toolUsed === 'get_tax_lines') return <TaxTable payload={payload} />;
  if (toolUsed === 'compare_periods') return <CompareTable payload={payload} />;
  if (toolUsed === 'get_recurring_discrepancies') return <RecurringTable payload={payload} />;
  if (toolUsed === 'get_high_priority_exceptions') return <ExceptionTable payload={payload} />;
  if (toolUsed === 'get_forecast' || toolUsed === 'get_cash_position') return <CashVisual payload={payload} />;
  if (toolUsed === 'search_financial_records') return <SearchTable payload={payload} />;
  return null;
}

export function captionFromAnswer(text) {
  const cleaned = String(text || '').replace(/\*\*(.*?)\*\*/g, '$1').replace(/\s+/g, ' ').trim();
  if (!cleaned) return '';
  const match = cleaned.match(/^[^.!?\n]+[.!?]?/);
  const line = (match ? match[0] : cleaned).trim();
  return line.length > 180 ? `${line.slice(0, 177)}…` : line;
}
