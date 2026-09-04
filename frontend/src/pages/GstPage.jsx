import React from 'react';
import { ExceptionBadge } from '../components/ChatPanel';
import { useApp } from '../AppContext';
import { formatRupees } from '../lib/format';
import { useLanguage } from '../i18n/LanguageContext';

export default function GstPage() {
  const { taxLines, reconciliationRun, setSelectedExcId, setDashPage, selectedExcId } = useApp();
  const { t } = useLanguage();
  if (!reconciliationRun) {
    return (
      <div className="db-page">
        <div className="db-card" data-tour="gst-summary">
          <p className="db-table-empty" data-tour="gst-table">Reconcile a batch to inspect GST lines.</p>
        </div>
      </div>
    );
  }

  const expected = taxLines?.expected_gst_rupees || 0;
  const actual = taxLines?.actual_gst_rupees || taxLines?.gst_collected_rupees || 0;
  const max = Math.max(expected, actual, 1);
  const delta = taxLines?.delta_rupees || 0;

  return (
    <div className="db-page">
      <div className="bank-page-head">
        <div>
          <p className="bank-kicker">Tax ledger</p>
          <h2 className="db-page-title">{t('pages.gstTitle')}</h2>
          <p className="db-page-sub">{taxLines?.rate || 'GST is calculated on the processing fee, not on GMV.'} GSTIN 29AABCU9603R1ZX · current batch.</p>
        </div>
        <div className="bank-account-chip">
          <span>Filing status</span>
          <strong>{(taxLines?.mismatched_lines || 0) ? 'Exceptions open' : 'In balance'}</strong>
        </div>
      </div>
      <div className="bank-balance-strip bank-strip-tax" data-tour="gst-summary">
        <div>
          <span>Taxable amount (fee)</span>
          <strong>{formatRupees(taxLines?.taxable_amount_rupees)}</strong>
        </div>
        <div>
          <span>Expected GST</span>
          <strong>{formatRupees(expected)}</strong>
        </div>
        <div>
          <span>GST collected</span>
          <strong>{formatRupees(actual)}</strong>
        </div>
        <div className={delta ? 'is-alert' : ''}>
          <span>Difference</span>
          <strong>{formatRupees(delta)}</strong>
        </div>
      </div>
      <div className="bank-split">
        <div className="db-card bank-statement">
          <h3 className="db-card-title">Expected vs collected</h3>
          <div className="db-gst-bars">
            <div>
              <span>Expected</span>
              <div className="db-forecast-bar-track"><div className="db-forecast-bar" style={{ width: `${(expected / max) * 100}%` }} /></div>
              <strong>{formatRupees(expected)}</strong>
            </div>
            <div>
              <span>Collected</span>
              <div className="db-forecast-bar-track"><div className="db-forecast-bar" style={{ width: `${(actual / max) * 100}%`, background: '#10b981' }} /></div>
              <strong>{formatRupees(actual)}</strong>
            </div>
          </div>
          <p className="bank-footnote">{taxLines?.matched_lines || 0} lines in tolerance · GST is 18% of fee.</p>
        </div>
        <div className="db-card bank-meta">
          <h3 className="db-card-title">Account particulars</h3>
          <dl>
            <div><dt>GSTIN</dt><dd>29AABCU9603R1ZX</dd></div>
            <div><dt>Tax type</dt><dd>GST on processing fee</dd></div>
            <div><dt>Mismatched lines</dt><dd>{taxLines?.mismatched_lines || 0}</dd></div>
            <div><dt>Open tax exceptions</dt><dd>{taxLines?.unresolved_gst_exceptions || 0}</dd></div>
          </dl>
        </div>
      </div>
      <div className="db-card" data-tour="gst-table">
        <div className="bank-table-head">
          <h3 className="db-card-title">GST statement</h3>
          <span>Click a mismatched line to open Exceptions</span>
        </div>
        <table className="db-table bank-ledger">
          <thead>
            <tr>
              <th>Payment ID</th>
              <th>Fee</th>
              <th>Expected GST</th>
              <th>Actual GST</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {(taxLines?.lines || []).slice(0, 20).map((line) => (
              <tr
                key={line.payment_id}
                className={`${line.status === 'mismatch' ? 'db-exc-row' : ''} ${selectedExcId === line.payment_id ? 'db-row-selected' : ''}`}
                onClick={() => {
                  if (line.status === 'mismatch') {
                    setSelectedExcId(line.payment_id);
                    setDashPage('exceptions');
                  }
                }}
              >
                <td className="db-exc-id">{line.payment_id}</td>
                <td>{formatRupees(line.fee_rupees)}</td>
                <td>{formatRupees(line.expected_gst_rupees)}</td>
                <td>{formatRupees(line.actual_gst_rupees)}</td>
                <td>
                  {line.status === 'mismatch'
                    ? <ExceptionBadge type="tax_line_mismatch" />
                    : <span className="db-status-badge db-status-reconciled">matched</span>}
                </td>
              </tr>
            ))}
            {!(taxLines?.lines || []).length && (
              <tr><td colSpan="5" className="db-table-empty">Every GST line matches the configured rate on fee.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
