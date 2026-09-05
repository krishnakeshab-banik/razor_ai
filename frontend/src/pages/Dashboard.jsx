import React from 'react';
import { useApp } from '../AppContext';
import ChatPanel, { ExceptionBadge } from '../components/ChatPanel';
import DateRangeFilter, { MobileFilterPack } from '../components/DateRangeFilter';
import NotificationMenu from '../components/NotificationMenu';
import CashPositionPage from './CashPage';
import ChatPage from './ChatPage';
import GstPage from './GstPage';
import GuidePage from './GuidePage';
import KnowledgePage from './KnowledgePage';
import PaymentsPage from './PaymentsPage';
import WithdrawPage from './WithdrawPage';
import { evidenceLabel, formatAge, formatCompactRupees, formatDelta, formatEvidenceDetail, formatPaise, formatRupees, formatTimestamp, friendlyExplanation, matchPercent, titleCaseType } from '../lib/format';
import { api } from '../lib/api';
import { useTour } from '../tour/TourContext';
import { useLanguage } from '../i18n/LanguageContext';
import LanguageToggle from '../components/LanguageToggle';

function Pagination({ page, total, onPrev, onNext }) {
  if (total <= 1) return null;
  return (
    <div className="db-pagination-row">
      <button className="db-page-btn" disabled={page === 1} onClick={onPrev} type="button">Prev</button>
      <span className="db-pagination-meta">Page {page} / {total}</span>
      <button className="db-page-btn" disabled={page >= total} onClick={onNext} type="button">Next</button>
    </div>
  );
}

function homeGreeting(t) {
  const hour = new Date().getHours();
  if (hour < 12) return t('home.morning');
  if (hour < 17) return t('home.afternoon');
  return t('home.evening');
}

function changeTone(metric, delta) {
  const inverse = /exception|unresolved|gst|refund|delay|priority/.test(String(metric || ''));
  const up = Number(delta) > 0;
  if (inverse) return up ? 'bad' : 'good';
  return up ? 'good' : 'bad';
}

function HomePage() {
  const {
    metrics, reconciliationRun, exceptions, expandedExc, setExpandedExc,
    visibleAuditLogs, auditPage, setAuditPage, totalAuditPages, DASHBOARD_PAGE_SIZE, auditLogs,
    cash, closeReport, setDashPage, setSelectedExcId,
  } = useApp();
  const { t } = useLanguage();
  const [intel, setIntel] = React.useState(null);
  const [intelLoading, setIntelLoading] = React.useState(false);
  const [versus, setVersus] = React.useState('yesterday');

  React.useEffect(() => {
    if (!reconciliationRun) {
      setIntel(null);
      setIntelLoading(false);
      return undefined;
    }
    let cancelled = false;
    setIntelLoading(true);
    api.controllerOverview(versus).then((data) => {
      if (!cancelled) setIntel(data);
    }).catch(() => {
      if (!cancelled) setIntel(null);
    }).finally(() => {
      if (!cancelled) setIntelLoading(false);
    });
    return () => { cancelled = true; };
  }, [reconciliationRun, metrics, versus, exceptions.length]);

  const previewExceptions = exceptions.slice(0, 40);
  const openCount = reconciliationRun ? (metrics?.unresolved_exceptions ?? metrics?.exceptions ?? 0) : null;
  const numbers = intel?.briefing?.numbers || {};
  const health = intel?.health;
  const queue = intel?.action_queue || [];
  const changes = intel?.what_changed?.changes || [];
  const showDesk = Boolean(reconciliationRun);
  const deskPending = showDesk && intelLoading && !intel;
  const matchWidth = reconciliationRun ? Math.round((metrics?.match_rate || 0) * 100) : 0;
  const healthScore = health?.score ?? null;

  return (
    <div className="db-page">
      <div className="db-page-heading" data-tour="dashboard-overview">
        <div>
          <p className="bank-kicker">{homeGreeting(t)}</p>
          <h2 className="db-page-title">{t('home.title')}</h2>
          <p className="db-page-sub">
            {reconciliationRun
              ? t('home.summary', {
                payments: metrics?.total_records?.toLocaleString('en-IN') || 0,
                match: matchPercent(metrics),
                open: openCount,
              })
              : t('home.emptySub')}
          </p>
        </div>
        {reconciliationRun ? (
          <button className="db-topbar-cta" type="button" onClick={() => { setSelectedExcId(null); setDashPage('exceptions'); }}>
            {t('home.queue')}{openCount != null ? ` · ${openCount}` : ''}
          </button>
        ) : (
          <button className="db-ghost-btn" type="button" onClick={() => setDashPage('reconciliation')}>
            {t('home.loadBatch')}
          </button>
        )}
      </div>

      <div className="home-kpi-row" data-tour="dashboard-metrics">
        <div className="home-kpi">
          <span>{t('home.matchRate')}</span>
          <strong>{reconciliationRun ? matchPercent(metrics) : '—'}</strong>
          <div className="home-kpi-bar" aria-hidden="true"><i style={{ width: `${matchWidth}%` }} /></div>
          <small>{reconciliationRun ? t('home.matchHint') : t('home.runFirst')}</small>
        </div>
        <div className="home-kpi">
          <span>{t('home.gross')}</span>
          <strong>{reconciliationRun ? (numbers.gmv_rupees != null ? formatRupees(numbers.gmv_rupees) : (deskPending ? '…' : formatPaise(metrics?.amount_reconciled))) : '—'}</strong>
          <small>{metrics?.total_records != null ? t('home.records', { count: Number(metrics.total_records).toLocaleString('en-IN') }) : t('home.noBatch')}</small>
        </div>
        <div className="home-kpi">
          <span>{t('home.amountMatched')}</span>
          <strong>{reconciliationRun && metrics ? formatPaise(metrics.amount_reconciled) : '—'}</strong>
          <small>{t('home.settledClean')}</small>
        </div>
        <div className="home-kpi home-kpi-alert">
          <span>{t('home.openExceptions')}</span>
          <strong>{openCount ?? '—'}</strong>
          <small>{reconciliationRun && metrics?.amount_at_risk != null ? t('home.atRisk', { amount: formatPaise(metrics.amount_at_risk) }) : t('home.waitingBatch')}</small>
        </div>
      </div>

      {cash && (
        <button className="bank-balance-strip bank-strip-payout home-cash-strip" data-tour="dashboard-cash" onClick={() => setDashPage('cash')} type="button">
          <div><span>{t('home.availableCash')}</span><strong>{formatRupees(cash.available_rupees)}</strong></div>
          <div><span>{t('home.inTransit')}</span><strong>{formatRupees(cash.in_transit_rupees)}</strong></div>
          <div><span>{t('home.blocked')}</span><strong>{formatRupees(cash.blocked_rupees)}</strong></div>
          <div><span>{t('home.next7')}</span><strong>{formatRupees(cash.expected_7d_rupees)}</strong></div>
        </button>
      )}

      {showDesk && (
        <div className="home-desk">
          <section className="db-card home-queue-card" data-tour="dashboard-queue">
            <div className="db-card-title-row">
              <h3 className="db-card-title">{t('home.workQueue')}</h3>
              <span className="home-count-chip">{deskPending ? '…' : t('home.items', { count: queue.length })}</span>
            </div>
            {deskPending ? (
              <div className="home-skel-stack" aria-hidden="true">
                <div className="home-skel" /><div className="home-skel" /><div className="home-skel" />
              </div>
            ) : queue.length ? (
              <div className="home-queue">
                {queue.slice(0, 5).map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    className={`home-queue-row ops-priority-${String(item.priority || 'low').toLowerCase()}`}
                    onClick={() => {
                      setDashPage(item.href || 'exceptions');
                      if (item.focus_id) setSelectedExcId(item.focus_id);
                    }}
                  >
                    <span className="ops-priority-label home-priority">{item.priority}</span>
                    <div className="home-queue-copy">
                      <strong>{item.title}</strong>
                      <small>{item.next_step}</small>
                    </div>
                    <span className="home-queue-amt">{item.amount_rupees ? formatCompactRupees(item.amount_rupees) : 'Open'}</span>
                  </button>
                ))}
              </div>
            ) : (
              <p className="db-table-empty">No ranked actions. The books are clean.</p>
            )}
          </section>

          <div className="home-desk-side">
            <section className="db-card home-health-card">
              <div className="home-health-top">
                <div
                  className={`home-health-ring ${healthScore != null && healthScore < 70 ? 'is-warn' : ''}`}
                  style={{ '--score': healthScore ?? 0 }}
                  aria-label={healthScore != null ? `Health ${healthScore} of 100` : 'Health pending'}
                >
                  <span>{healthScore ?? '—'}</span>
                </div>
                <div>
                  <h3 className="db-card-title">Books health</h3>
                  <p className="text-dim">{deskPending ? 'Scoring this run…' : (health?.explanation || 'Score appears after the briefing loads.')}</p>
                </div>
              </div>
              {!deskPending && !!health?.deductions?.length && (
                <ul className="home-deductions">
                  {health.deductions.slice(0, 3).map((item) => (
                    <li key={item.reason}><span>−{item.points}</span>{item.reason}</li>
                  ))}
                </ul>
              )}
            </section>
            <section className="db-card">
              <div className="db-card-title-row">
                <h3 className="db-card-title">What changed</h3>
                <select className="db-filter-select" value={versus} onChange={(event) => setVersus(event.target.value)}>
                  <option value="yesterday">Yesterday</option>
                  <option value="7d">Previous 7 days</option>
                  <option value="previous_batch">Previous batch</option>
                  <option value="comparable">Comparable week</option>
                </select>
              </div>
              {deskPending ? (
                <div className="home-skel-stack" aria-hidden="true">
                  <div className="home-skel" /><div className="home-skel" />
                </div>
              ) : changes.length ? (
                <ul className="home-changes">
                  {changes.slice(0, 5).map((change) => (
                    <li key={`${change.metric}-${change.headline}`} className={changeTone(change.metric, change.delta)}>
                      <em>{Number(change.delta) > 0 ? '▲' : '▼'}</em>
                      <span>{change.title}</span>
                      <strong>{String(change.headline || change.title || '').replace(`${change.title || ''} `, '')}</strong>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="db-table-empty">{intel?.what_changed?.note || 'No financially important changes in this window.'}</p>
              )}
            </section>
          </div>
        </div>
      )}

      {reconciliationRun && metrics && (
        <div className="home-secondary">
          <div><span>Throughput</span><strong>{(metrics.records_per_second || 0).toLocaleString('en-IN')}/s</strong><small>{metrics.processing_time_seconds != null ? `${Number(metrics.processing_time_seconds).toFixed(3)}s reconcile()` : 'measured'}</small></div>
          <div><span>Auto-resolved</span><strong>{metrics.resolved_count ?? 0}</strong></div>
          <div><span>Human review</span><strong>{metrics.escalated_count ?? 0}</strong></div>
          <div><span>GST issues</span><strong>{numbers.gst_issues ?? '—'}</strong></div>
        </div>
      )}

      {metrics?.validation && (
        <div className="db-engine-banner">
          <div>
            <span className="db-engine-kicker">Engine validation</span>
            <p>Measured against the hidden answer key. Detection stays honest after close.</p>
          </div>
          <div className="db-engine-pills">
            <span>Seeded <strong>{metrics.validation.seeded_mismatches}</strong></span>
            <span>Detected <strong className="db-engine-green">{metrics.validation.correctly_detected} ({(metrics.validation.detection_rate * 100).toFixed(0)}%)</strong></span>
            <span>False positives <strong>{metrics.validation.false_positives}</strong></span>
          </div>
        </div>
      )}

      {closeReport && (
        <div className="validation-banner">
          <span className="validation-badge">Books closed</span>
          <div className="validation-metrics">
            <span>Auto-resolved <strong>{closeReport.auto_resolved}</strong></span>
            <span>Remaining <strong>{closeReport.remaining_exceptions.length}</strong></span>
            <span>Final match <strong>{matchPercent(closeReport.final)}</strong></span>
          </div>
        </div>
      )}

      <div className="db-home-body">
        <div className="db-card db-exceptions-card" data-tour="dashboard-exceptions">
          <div className="db-card-title-row">
            <h3 className="db-card-title">Open exceptions</h3>
            <div className="db-card-title-actions">
              <span className="db-muted">{reconciliationRun ? `${exceptions.length} open` : 'Not reconciled'}</span>
              {exceptions.length > 0 && (
                <button className="db-text-link" type="button" onClick={() => setDashPage('exceptions')}>
                  {exceptions.length > 8 ? `View all ${exceptions.length}` : 'Open queue'}
                </button>
              )}
            </div>
          </div>
          <div className="db-exceptions-scroll">
          <table className="db-table mobile-cards">
            <thead>
              <tr>
                <th>Payment ID</th>
                <th>Issue</th>
                <th>Delta</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {previewExceptions.length ? previewExceptions.map((exc) => (
                <React.Fragment key={exc.payment_id}>
                  <tr className={`db-exc-row ${expandedExc === exc.payment_id ? 'expanded' : ''}`} onClick={() => setExpandedExc(expandedExc === exc.payment_id ? null : exc.payment_id)}>
                    <td data-label="Payment ID" className="db-exc-id">{exc.payment_id}</td>
                    <td data-label="Issue"><ExceptionBadge type={exc.mismatch_type} /></td>
                    <td data-label="Delta">{exc.delta !== null && exc.delta !== undefined ? <span className="db-delta-pill">{formatDelta(exc.delta)}</span> : <span className="db-delta-pill muted">No delta</span>}</td>
                    <td data-label="Action" className="db-exc-chevron">{expandedExc === exc.payment_id ? 'Hide' : 'Open'}</td>
                  </tr>
                  {expandedExc === exc.payment_id && (
                    <tr className="db-exc-detail-row">
                      <td colSpan="4">
                        <div className="db-exc-detail">
                          <span>{exc.explanation}</span>
                        </div>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              )) : (
                <tr><td colSpan="4" className="db-table-empty">{reconciliationRun ? 'No open exceptions. The books are clean.' : 'Load and reconcile a batch to begin.'}</td></tr>
              )}
            </tbody>
          </table>
          </div>
        </div>
        <ChatPanel />
      </div>

      <div className="db-card db-audit-section">
        <div className="db-audit-header">
          <h3 className="db-card-title">Audit trail</h3>
          <div className="db-audit-legend">
            <span className="db-legend-dot db-legend-engine" /> Rule engine
            <span className="db-legend-dot db-legend-razorpay" style={{ marginLeft: 12 }} /> Razorpay test
            <span className="db-legend-dot db-legend-ai" style={{ marginLeft: 12 }} /> Gemini
          </div>
        </div>
        <div className="db-audit-list">
          {(visibleAuditLogs || []).length ? visibleAuditLogs.map((log) => {
            const time = new Date(log.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: true }).toUpperCase();
            const isAI = log.source === 'gemini_api';
            const isRazorpay = log.source === 'razorpay_test_api';
            const details = String(log.details || '');
            const actor = isAI
              ? 'Gemini'
              : isRazorpay
                ? 'Razorpay test'
                : (log.source === 'ops_controller' ? 'Controller' : log.source === 'ecommerce_demo' ? 'Store demo' : 'Rule engine');
            return (
              <div key={log.id} className="db-audit-row">
                <span className="db-audit-time">{time}</span>
                <span className={`db-audit-dot ${isAI ? 'db-legend-ai' : isRazorpay ? 'db-legend-razorpay' : 'db-legend-engine'}`} />
                <span className="db-audit-text">
                  {actor}: {details.length > 90 ? `${details.slice(0, 90)}…` : details}
                </span>
              </div>
            );
          }) : (
            <div className="db-table-empty">No audit logs yet.</div>
          )}
        </div>
        {auditLogs.length > DASHBOARD_PAGE_SIZE && (
          <Pagination
            page={auditPage}
            total={totalAuditPages}
            onPrev={() => setAuditPage((page) => Math.max(1, page - 1))}
            onNext={() => setAuditPage((page) => Math.min(totalAuditPages, page + 1))}
          />
        )}
      </div>
    </div>
  );
}

function ReconciliationPage() {
  const {
    batchInputRef, handleBatchFileSelection, handleDropBatch, downloadBatchTemplate,
    handleRunReconciliation, handleGenerateFresh, generateCount, setGenerateCount,
    isConnected, batchLoaded, reconciliationRun, metrics, ingestReport,
  } = useApp();
  const { t } = useLanguage();

  return (
    <div className="db-page">
      <div className="db-page-heading">
        <div>
          <h2 className="db-page-title">{t('pages.reconTitle')}</h2>
          <p className="db-page-sub">{t('pages.reconSub')}</p>
        </div>
      </div>
      <div className="db-recon-layout">
        <div className="db-card db-upload-card">
          <h3 className="db-card-title">New batch</h3>
          <div
            className="db-upload-zone"
            onDragOver={(event) => event.preventDefault()}
            onDrop={handleDropBatch}
          >
            <input ref={batchInputRef} type="file" accept=".csv,.xlsx,.txt" hidden onChange={handleBatchFileSelection} />
            <p className="db-upload-text">Drop a Razorpay export</p>
            <p className="db-upload-sub">CSV / XLSX / TXT · amounts may be rupees or paise · template included</p>
            <div className="db-upload-actions">
              <button className="db-upload-btn db-upload-btn-muted" onClick={downloadBatchTemplate} type="button">Download template</button>
              <button className="db-upload-btn db-upload-btn-primary" onClick={() => batchInputRef.current?.click()} disabled={!isConnected} type="button">Browse files</button>
              <button className="db-upload-btn db-upload-btn-primary sticky-page-cta" data-tour="reconciliation-run" onClick={() => handleRunReconciliation({ force: true })} disabled={!isConnected || !batchLoaded} type="button">
                {reconciliationRun ? 'Re-run engine' : 'Run reconciliation'}
              </button>
            </div>
            <div className="db-generate-row">
              <select className="db-filter-select" value={generateCount} onChange={(event) => setGenerateCount(Number(event.target.value))}>
                <option value={50}>50 records</option>
                <option value={100}>100 records</option>
                <option value={250}>250 records</option>
                <option value={500}>500 records</option>
                <option value={1000}>1000 records</option>
              </select>
              <button className="db-upload-btn db-upload-btn-primary" data-tour="reconciliation-generate" onClick={handleGenerateFresh} disabled={!isConnected} type="button">
                Generate Demo Dataset
              </button>
            </div>
          </div>
          <div className="db-upload-footer">
            <span>Paise-accurate arithmetic</span>
            <span className="db-ai-assisted">Gemini only on Q&A</span>
          </div>
          {ingestReport && (
            <div className="db-ingest-report">
              <strong>Ingest report</strong>
              <p>Source: {ingestReport.detected_source || 'combined export'} · {ingestReport.row_count} rows · {ingestReport.units}</p>
              {!!ingestReport.detected_columns?.length && (
                <p className="text-dim">Detected columns: {ingestReport.detected_columns.join(', ')}</p>
              )}
              {!!ingestReport.missing_required?.length && (
                <p className="db-ingest-bad">Missing required: {ingestReport.missing_required.join(', ')}</p>
              )}
              {!!ingestReport.warnings?.length && (
                <ul>{ingestReport.warnings.map((item) => <li key={item}>{item}</li>)}</ul>
              )}
              {!!ingestReport.malformed_count && (
                <p className="db-ingest-bad">{ingestReport.malformed_count} malformed rows were kept and flagged — nothing was silently dropped.</p>
              )}
              {!!ingestReport.malformed_rows?.length && (
                <ul>
                  {ingestReport.malformed_rows.slice(0, 8).map((row) => (
                    <li key={`${row.row}-${row.field}`}>{`Row ${row.row} · ${row.field}: ${row.issue} (${row.value})`}</li>
                  ))}
                </ul>
              )}
              {!!ingestReport.preview?.length && (
                <table className="db-table mobile-cards">
                  <thead>
                    <tr>
                      {Object.keys(ingestReport.preview[0]).map((col) => <th key={col}>{col}</th>)}
                    </tr>
                  </thead>
                  <tbody>
                    {ingestReport.preview.map((row, idx) => (
                      <tr key={row.payment_id || idx}>
                        {Object.keys(ingestReport.preview[0]).map((col) => <td key={col} data-label={col}>{String(row[col] ?? '')}</td>)}
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          )}
        </div>
          <div className="db-recon-right">
          <div className="db-recon-summary" data-tour="reconciliation-results">
            <div className="db-recon-sum-card">
              <div>
                <span className="db-recon-sum-label">Matched</span>
                <div className="db-recon-sum-val">{reconciliationRun && metrics ? formatPaise(metrics.amount_reconciled) : '₹0'}</div>
              </div>
            </div>
            <div className="db-recon-sum-card">
              <div>
                <span className="db-recon-sum-label">Active batch</span>
                <div className="db-recon-sum-val">{batchLoaded ? '1' : '0'}</div>
              </div>
            </div>
            <div className="db-recon-sum-card">
              <div>
                <span className="db-recon-sum-label">Needs attention</span>
                <div className="db-recon-sum-val">{reconciliationRun ? (metrics?.unresolved_exceptions ?? metrics?.exceptions) : '0'}</div>
              </div>
            </div>
          </div>
          <div className="db-card">
            <h3 className="db-card-title">Current batch</h3>
            <p className="db-card-sub">Stable ID — not regenerated on every render</p>
            <table className="db-table mobile-cards">
              <thead>
                <tr>
                  <th>Batch ID</th>
                  <th>Loaded</th>
                  <th>Status</th>
                  <th>Match rate</th>
                  <th>Source</th>
                </tr>
              </thead>
              <tbody>
                {batchLoaded && metrics?.batch ? (
                  <tr>
                    <td data-label="Batch ID"><strong>{metrics.batch.batch_id}</strong></td>
                    <td data-label="Loaded">{new Date(metrics.batch.loaded_at).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' })}</td>
                    <td data-label="Status">
                      <span className={`db-status-badge ${reconciliationRun ? 'db-status-reconciled' : 'db-status-pending'}`}>
                        {reconciliationRun ? 'Reconciled' : 'Pending'}
                      </span>
                    </td>
                    <td data-label="Match rate">
                      <div className="db-match-bar-wrap">
                        <div className="db-match-bar" style={{ width: reconciliationRun ? `${(metrics.match_rate || 0) * 100}%` : '0%', backgroundColor: reconciliationRun ? '#10b981' : '#f59e0b' }} />
                        <span>{reconciliationRun ? matchPercent(metrics) : '—'}</span>
                      </div>
                    </td>
                    <td data-label="Source">{metrics.batch.source}</td>
                  </tr>
                ) : (
                  <tr><td colSpan="5" className="db-table-empty">No batch loaded.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}

function ExceptionsPage() {
  const {
    mismatchFilter, setMismatchFilter, pagedExceptions, filteredExceptions,
    selectedExcId, setSelectedExcId, selectedException, exceptionPage, setExceptionPage,
    totalExceptionPages, reconciliationRun, handleResolveException, resolvingId,
    handleRunReconciliation, isConnected, batchLoaded, searchQuery, setSearchQuery,
    handleInvestigate, handleExplainDifference, investigation, difference,
    exceptionFilter, setExceptionFilter, exceptionSearch, triggerToast,
  } = useApp();
  const { t } = useLanguage();
  const [analystNote, setAnalystNote] = React.useState('');
  const [remember, setRemember] = React.useState(false);
  const [workflow, setWorkflow] = React.useState('all');
  const [clusters, setClusters] = React.useState([]);
  const [clusterPreview, setClusterPreview] = React.useState(null);
  const [timeline, setTimeline] = React.useState(null);
  const [rightTab, setRightTab] = React.useState('details');
  const [panelOpen, setPanelOpen] = React.useState(false);

  React.useEffect(() => {
    if (!reconciliationRun) return undefined;
    api.clusters().then((data) => setClusters(Array.isArray(data) ? data : [])).catch(() => setClusters([]));
    return undefined;
  }, [reconciliationRun, filteredExceptions.length]);

  React.useEffect(() => {
    if (!selectedExcId) {
      setTimeline(null);
      return undefined;
    }
    api.timeline(selectedExcId).then(setTimeline).catch(() => setTimeline(null));
    return undefined;
  }, [selectedExcId]);

  const openPanel = (tab = 'details') => {
    setRightTab(tab);
    setPanelOpen(true);
  };

  const closePanel = () => setPanelOpen(false);

  React.useEffect(() => {
    if (selectedExcId) setPanelOpen(true);
    else setPanelOpen(false);
  }, [selectedExcId]);

  React.useEffect(() => {
    const onTourPanel = (event) => openPanel(event.detail || 'details');
    window.addEventListener('razor-open-exception-panel', onTourPanel);
    return () => window.removeEventListener('razor-open-exception-panel', onTourPanel);
  }, []);

  React.useEffect(() => {
    if (!panelOpen) return undefined;
    const onKey = (event) => {
      if (event.key === 'Escape') closePanel();
    };
    const previousOverflow = document.body.style.overflow;
    document.addEventListener('keydown', onKey);
    document.body.style.overflow = 'hidden';
    return () => {
      document.removeEventListener('keydown', onKey);
      document.body.style.overflow = previousOverflow;
    };
  }, [panelOpen]);

  const unreviewed = filteredExceptions.filter((item) => !item.resolution || item.workflow_status === 'Open' || item.workflow_status === 'Unreviewed');
  const shown = workflow === 'unreviewed' ? pagedExceptions.filter((item) => unreviewed.some((row) => row.payment_id === item.payment_id)) : pagedExceptions;

  const previewCluster = async (cluster) => {
    try {
      const data = await api.batchResolve({ cluster_id: cluster.cluster_id, action: cluster.suggested_action || 'apply_fix', confirm: false });
      setClusterPreview({ cluster, ...data });
    } catch (error) {
      triggerToast(error.message || 'Could not preview cluster.', 'danger');
    }
  };

  const confirmCluster = async () => {
    if (!clusterPreview) return;
    try {
      const data = await api.batchResolve({
        cluster_id: clusterPreview.cluster.cluster_id,
        action: clusterPreview.action,
        confirm: true,
        remember,
        note: analystNote,
      });
      triggerToast(`Batch resolved ${data.applied.length} records. ${data.skipped.length} skipped.`, data.skipped.length ? 'warning' : 'success');
      setClusterPreview(null);
      handleRunReconciliation({ force: true });
    } catch (error) {
      triggerToast(error.message || 'Batch resolve rejected.', 'danger');
    }
  };

  return (
    <div className="db-page">
      <div className="db-page-heading">
        <div>
          <h2 className="db-page-title">{t('pages.exceptionsTitle')}</h2>
          <p className="db-page-sub">{t('pages.exceptionsSub')}</p>
        </div>
        <span className="db-heading-count">{exceptionSearch?.totals?.count ?? filteredExceptions.length} shown</span>
      </div>
      <div data-tour="exceptions-filter">
      <DateRangeFilter value={exceptionFilter} onChange={setExceptionFilter} dataTour="exceptions-date" />
      {exceptionSearch?.filter?.warning && <p className="db-ingest-bad">{exceptionSearch.filter.warning}</p>}
      {exceptionSearch?.totals && (
        <div className="db-stats-row">
          <div className="db-stat-card"><span className="db-stat-label">Exceptions</span><div className="db-stat-value">{exceptionSearch.totals.count}</div></div>
          <div className="db-stat-card db-stat-card-alert"><span className="db-stat-label">Amount affected</span><div className="db-stat-value">{formatRupees(exceptionSearch.totals.amount_rupees)}</div></div>
          <div className="db-stat-card"><span className="db-stat-label">High / Critical</span><div className="db-stat-value">{(exceptionSearch.totals.high || 0) + (exceptionSearch.totals.critical || 0)}</div></div>
        </div>
      )}
      <div className="db-exc-filters">
        <input
          className="db-exc-search"
          value={searchQuery}
          onChange={(event) => setSearchQuery(event.target.value)}
          placeholder="Search payment ID, type, or explanation…"
        />
        <select className="db-filter-select" value={mismatchFilter} onChange={(event) => setMismatchFilter(event.target.value)}>
          <option value="all">All mismatch types</option>
          <option value="missing_settlement">Missing settlement</option>
          <option value="unaccounted_refund">Unaccounted refund</option>
          <option value="fee_miscalculation">Fee miscalculation</option>
          <option value="tax_line_mismatch">GST line mismatch</option>
          <option value="duplicate_record">Duplicate record</option>
          <option value="timing_mismatch">Timing mismatch</option>
          <option value="partial_settlement">Partial settlement</option>
          <option value="unknown_adjustment">Unknown adjustment</option>
        </select>
        <button className="db-filter-btn" onClick={() => handleRunReconciliation({ force: true })} disabled={!isConnected || !batchLoaded} type="button">
          Re-run engine
        </button>
      </div>
      </div>
      <div className="ops-console">
        <aside className="ops-rail">
          <div className="ops-rail-group">
            <span>Run results</span>
            <button type="button" className={workflow === 'all' ? 'active' : ''} onClick={() => setWorkflow('all')}>
              All trades <em>{exceptionSearch?.totals?.count ?? filteredExceptions.length}</em>
            </button>
            <button type="button" className={workflow === 'unreviewed' ? 'active' : ''} onClick={() => setWorkflow('unreviewed')}>
              Unreviewed <em className="ops-badge-red">{unreviewed.length}</em>
            </button>
          </div>
          <div className="ops-rail-group">
            <span>Matching</span>
            <button type="button" className={mismatchFilter === 'all' ? 'active' : ''} onClick={() => setMismatchFilter('all')}>
              Exceptions <em>{filteredExceptions.length}</em>
            </button>
            {clusters.slice(0, 6).map((cluster) => (
              <button key={cluster.cluster_id} type="button" onClick={() => previewCluster(cluster)}>
                {titleCaseType(cluster.mismatch_type)}{cluster.payment_methods?.filter((method) => method && method !== 'unknown').length ? ` · ${cluster.payment_methods.filter((method) => method && method !== 'unknown').join('/')}` : ''} <em>{cluster.count}</em>
              </button>
            ))}
          </div>
        </aside>
        <div className="db-card ops-table-card" data-tour="exceptions-list">
          <table className="db-table ops-table mobile-cards">
            <thead>
              <tr>
                <th>ID</th>
                <th>Workflow</th>
                <th>Match status</th>
                <th>Score</th>
                <th>Issue</th>
                <th>Priority</th>
                <th>Captured</th>
                <th>Expected vs credited</th>
                <th>Age</th>
              </tr>
            </thead>
            <tbody>
              {shown.length ? shown.map((exc) => {
                const mismatch = exc.expected_settlement != null && exc.settlement_amount != null && exc.expected_settlement !== exc.settlement_amount;
                return (
                  <tr key={exc.payment_id} className={selectedExcId === exc.payment_id ? 'db-row-selected' : ''} onClick={() => { setSelectedExcId(exc.payment_id); openPanel('details'); }}>
                    <td data-label="ID"><button type="button" className="ops-id-link" onClick={(event) => { event.stopPropagation(); setSelectedExcId(exc.payment_id); openPanel('details'); }}>{exc.payment_id}</button></td>
                    <td data-label="Workflow"><span className={`ops-workflow-pill ${(exc.workflow_status || 'Unreviewed').toLowerCase().replace(/\s+/g, '-')}`}>{exc.workflow_status || 'Unreviewed'}</span></td>
                    <td data-label="Match status">{exc.open ? (mismatch ? 'Partially matched' : 'Unmatched') : 'Matched'}</td>
                    <td data-label="Score">{Math.round((exc.confidence || 0) * 100)}%</td>
                    <td data-label="Issue">{titleCaseType(exc.mismatch_type)}</td>
                    <td data-label="Priority"><span className={`db-priority-badge db-priority-${(exc.priority || 'Low').toLowerCase()}`}>{exc.priority || 'Low'}</span></td>
                    <td data-label="Captured">{formatTimestamp(exc.created_at)}</td>
                    <td data-label="Expected vs credited" className={mismatch ? 'ops-cell-mismatch' : ''}>
                      {mismatch ? <small>{formatPaise(exc.expected_settlement)} vs {formatPaise(exc.settlement_amount)}</small> : '—'}
                    </td>
                    <td data-label="Age">{formatAge(exc.created_at)}</td>
                  </tr>
                );
              }) : (
                <tr><td colSpan="9" className="db-table-empty">{reconciliationRun ? 'No exceptions match this filter.' : 'Load and reconcile a batch first.'}</td></tr>
              )}
            </tbody>
          </table>
          <Pagination
            page={exceptionPage}
            total={totalExceptionPages}
            onPrev={() => setExceptionPage((page) => Math.max(1, page - 1))}
            onNext={() => setExceptionPage((page) => Math.min(totalExceptionPages, page + 1))}
          />
          <p className="exc-table-hint">Click a payment ID to open suggested resolution. Details, actions and filters appear in that panel.</p>
        </div>
      </div>
      {clusterPreview && (
        <div className="db-card">
          <h3 className="db-card-title">Resolve {clusterPreview.count} exceptions</h3>
          <p>{clusterPreview.expected_effect}</p>
          <p>Root cause: {clusterPreview.root_cause?.label} — {clusterPreview.root_cause?.cause}</p>
          <p>Confidence {Math.round((clusterPreview.ai_confidence || 0) * 100)}% · {formatRupees(clusterPreview.total_amount_rupees)}</p>
          <div className="db-exc-filters">
            <button className="db-filter-btn" type="button" onClick={confirmCluster}>Confirm batch resolve</button>
            <button className="db-ghost-btn" type="button" onClick={() => setClusterPreview(null)}>Cancel</button>
          </div>
        </div>
      )}
      {panelOpen && (
        <div className="exc-overlay" role="dialog" aria-modal="true" aria-labelledby="exc-sheet-title">
          <button type="button" className="exc-overlay-backdrop" aria-label="Close suggested resolution" onClick={closePanel} />
          <div className="exc-sheet">
            <header className="exc-sheet-head">
              <div>
                <p className="exc-sheet-kicker">Suggested resolution</p>
                <h3 id="exc-sheet-title">{selectedException?.payment_id || 'Exception workdesk'}</h3>
                {selectedException && (
                  <p>{titleCaseType(selectedException.mismatch_type)} · {selectedException.priority} priority · {selectedException.workflow_status || 'Unreviewed'}</p>
                )}
              </div>
              {selectedException?.suggested_action?.label && (
                <span className="exc-suggest-chip">{selectedException.suggested_action.label}</span>
              )}
              <button type="button" className="exc-sheet-close" onClick={closePanel}>✕</button>
            </header>
            <div className="exc-sheet-tabs">
              <button type="button" className={rightTab === 'details' ? 'active' : ''} onClick={() => setRightTab('details')}>Details</button>
              <button type="button" className={rightTab === 'actions' ? 'active' : ''} onClick={() => setRightTab('actions')}>Actions</button>
              <button type="button" className={rightTab === 'filter' ? 'active' : ''} onClick={() => setRightTab('filter')}>Filter</button>
            </div>
            <div className="exc-sheet-body">
              {rightTab === 'filter' && (
                <div className="exc-filter-pane">
                  <p className="db-page-sub">Narrow the queue without leaving this panel.</p>
                  <DateRangeFilter value={exceptionFilter} onChange={setExceptionFilter} />
                  <input className="db-exc-search" value={searchQuery} onChange={(event) => setSearchQuery(event.target.value)} placeholder="Search payment ID, type, or explanation…" />
                  <select className="db-filter-select" value={mismatchFilter} onChange={(event) => setMismatchFilter(event.target.value)}>
                    <option value="all">All mismatch types</option>
                    <option value="missing_settlement">Missing settlement</option>
                    <option value="unaccounted_refund">Unaccounted refund</option>
                    <option value="fee_miscalculation">Fee miscalculation</option>
                    <option value="tax_line_mismatch">GST line mismatch</option>
                    <option value="duplicate_record">Duplicate record</option>
                    <option value="timing_mismatch">Timing mismatch</option>
                    <option value="partial_settlement">Partial settlement</option>
                    <option value="unknown_adjustment">Unknown adjustment</option>
                  </select>
                  <div className="db-whatif-actions">
                    <button type="button" className={workflow === 'all' ? 'db-topbar-cta' : 'db-filter-btn'} onClick={() => setWorkflow('all')}>All trades</button>
                    <button type="button" className={workflow === 'unreviewed' ? 'db-topbar-cta' : 'db-filter-btn'} onClick={() => setWorkflow('unreviewed')}>Unreviewed only</button>
                  </div>
                </div>
              )}
              {rightTab !== 'filter' && !selectedException && (
                <p className="db-ai-empty">Click a payment ID in the table to inspect it here.</p>
              )}
              {rightTab === 'details' && selectedException && (
                <div className="exc-details-pane">
                  <div className="bank-stat-row" data-tour="exception-ledger">
                    <div><span>Gross</span><strong>{formatPaise(selectedException.amount)}</strong></div>
                    <div><span>Settlement</span><strong>{formatPaise(selectedException.settlement_amount)}</strong></div>
                    <div><span>Fee</span><strong>{formatPaise(selectedException.fee)}</strong></div>
                    <div><span>GST</span><strong>{formatPaise(selectedException.tax)}</strong></div>
                    <div><span>Refund</span><strong>{formatPaise(selectedException.refund_amount)}</strong></div>
                    <div><span>Suggested</span><strong>{selectedException.suggested_action?.label || 'Human review'}</strong></div>
                  </div>
                  <div className="exc-diagnosis">
                    <span>Diagnosis</span>
                    <p>{friendlyExplanation(selectedException.explanation)}</p>
                  </div>
                  {!!selectedException.evidence?.length && (
                    <div className="exc-evidence">
                      <div className="exc-evidence-head">
                        <strong>Evidence</strong>
                        <span>{Math.round((selectedException.confidence || 0) * 100)}% confidence</span>
                      </div>
                      <ul>
                        {selectedException.evidence.map((item) => (
                          <li key={item.signal} className={item.matched ? 'is-ok' : 'is-miss'}>
                            <em>{item.matched ? 'Pass' : 'Gap'}</em>
                            <div>
                              <strong>{evidenceLabel(item.signal)}</strong>
                              <p>{formatEvidenceDetail(item.detail)}</p>
                            </div>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                  <div className="db-whatif-actions">
                    <button className="db-topbar-cta" type="button" data-tour="exception-explain" onClick={() => handleExplainDifference(selectedException.payment_id)}>Explain this difference</button>
                    <button className="db-filter-btn" type="button" data-tour="exception-investigate" onClick={() => handleInvestigate(selectedException.payment_id)}>Investigate exception</button>
                  </div>
                  {difference && difference.payment_id === selectedException.payment_id && (
                    <div className="db-waterfall">
                      <div className={`db-waterfall-status ${difference.fully_explained ? 'ok' : 'warn'}`}>{difference.status}</div>
                      {difference.steps.map((step) => (
                        <div className="db-waterfall-row" key={step.id}>
                          <span>{step.label}</span>
                          <strong>{step.missing ? 'Missing' : formatRupees(step.rupees)}</strong>
                        </div>
                      ))}
                    </div>
                  )}
                  {investigation && investigation.payment_id === selectedException.payment_id && (
                    <div className="db-investigation">
                      <p><strong>Most likely cause:</strong> {(investigation.most_likely_cause?.cause || '').replace(/_/g, ' ')} ({Math.round((investigation.confidence || 0) * 100)}% confidence)</p>
                      <p>{investigation.recommended_action}</p>
                      <p className="text-dim">{investigation.ai_note}</p>
                    </div>
                  )}
                  {timeline?.events?.length ? (
                    <div className="exc-timeline">
                      <h4>Transaction timeline</h4>
                      {timeline.events.map((event, idx) => (
                        <div className="exc-timeline-item" key={`${event.event_type}-${idx}`}>
                          <i aria-hidden="true" />
                          <div>
                            <strong>{titleCaseType(event.event_type)}</strong>
                            <p>{event.record_id || '—'}</p>
                            <time>{formatTimestamp(event.timestamp)}</time>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : null}
                </div>
              )}
              {rightTab === 'actions' && selectedException && (
                <div className="exc-actions-pane" data-tour="exception-resolve">
                  <p className="exc-actions-note">These buttons change the books. Missing settlements cannot be auto-fixed.</p>
                  <label className="merchant-check-row">
                    <input type="checkbox" checked={remember} onChange={() => setRemember((value) => !value)} />
                    Remember this resolution pattern
                  </label>
                  {selectedException.suggested_action?.auto_fixable ? (
                    <button className="exc-action-card exc-action-card-primary" type="button" disabled={resolvingId === selectedException.payment_id} onClick={() => handleResolveException(selectedException.payment_id, 'apply_fix', analystNote, remember)}>
                      <div>
                        <strong>Apply suggested fix</strong>
                        <p>{selectedException.suggested_action.detail}</p>
                      </div>
                    </button>
                  ) : (
                    <div className="exc-human-review">Human review required. This break cannot be auto-fixed without inventing a bank credit.</div>
                  )}
                  <button className="exc-action-card" type="button" disabled={resolvingId === selectedException.payment_id} onClick={() => handleResolveException(selectedException.payment_id, 'acknowledge')}>
                    <div><strong>Acknowledge</strong><p>Mark investigating. Stays open on the exception list.</p></div>
                  </button>
                  <button className="exc-action-card" type="button" disabled={resolvingId === selectedException.payment_id} onClick={() => handleResolveException(selectedException.payment_id, 'escalate')}>
                    <div><strong>Escalate / send for human review</strong><p>Keep it on the honest exception list for a human chase.</p></div>
                  </button>
                  <button className="exc-action-card exc-action-card-warn" type="button" disabled={resolvingId === selectedException.payment_id} onClick={() => handleResolveException(selectedException.payment_id, 'waive', analystNote, remember)}>
                    <div><strong>Resolve manually / waive</strong><p>Human override after review. Audited. Does not invent a UTR.</p></div>
                  </button>
                  <button className="exc-action-card" type="button" disabled={resolvingId === selectedException.payment_id} onClick={() => handleResolveException(selectedException.payment_id, 'reject', analystNote)}>
                    <div><strong>Reject AI recommendation</strong><p>Keep the exception open and record the disagreement.</p></div>
                  </button>
                  <button className="exc-action-card" type="button" disabled={resolvingId === selectedException.payment_id} onClick={() => handleResolveException(selectedException.payment_id, 'reopen')}>
                    <div><strong>Reopen</strong><p>Clear a prior resolution stamp and put it back in the queue.</p></div>
                  </button>
                  <label className="db-card-sub" htmlFor="analyst-note">Analyst note</label>
                  <textarea id="analyst-note" className="db-exc-search" rows={2} value={analystNote} onChange={(event) => setAnalystNote(event.target.value)} placeholder="Optional note stored in the audit trail…" />
                  <button className="exc-action-card" type="button" disabled={resolvingId === selectedException.payment_id || !analystNote.trim()} onClick={() => { handleResolveException(selectedException.payment_id, 'add_note', analystNote); setAnalystNote(''); }}>
                    <div><strong>Add note</strong><p>Appends to the immutable audit trail. Does not change financial truth.</p></div>
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function CashPage() {
  const { cash, sources, taxLines, closeReport, reconciliationRun, handleWhatIf, whatIfResult } = useApp();
  if (!reconciliationRun) {
    return <div className="db-page"><div className="db-card"><p className="db-table-empty">Reconcile a batch to see cash, GST lines and three-way breaks.</p></div></div>;
  }

  const maxInflow = Math.max(1, ...(cash?.forecast || []).map((day) => day.expected_inflow_rupees));

  return (
    <div className="db-page">
      <div>
        <h2 className="db-page-title">Cash position</h2>
        <p className="db-page-sub">Captured is not settled. This is the T+2 view a Razorpay merchant actually needs.</p>
      </div>
      <div className="db-reports-summary-row">
        <div className="db-report-highlight-card db-report-highlight-green">
          <span className="db-report-kicker">Available</span>
          <strong>{formatRupees(cash?.available_rupees)}</strong>
          <small>Matched and past settled_at</small>
        </div>
        <div className="db-report-highlight-card db-report-highlight-blue">
          <span className="db-report-kicker">In transit</span>
          <strong>{formatRupees(cash?.in_transit_rupees)}</strong>
          <small>All matched settlements not yet received</small>
        </div>
        <div className="db-report-highlight-card db-report-highlight-amber">
          <span className="db-report-kicker">Blocked</span>
          <strong>{formatRupees(cash?.blocked_rupees)}</strong>
          <small>Still sitting in open exceptions</small>
        </div>
        <div className="db-report-highlight-card db-report-highlight-violet">
          <span className="db-report-kicker">Next 7 days</span>
          <strong>{formatRupees(cash?.expected_7d_rupees)}</strong>
          <small>Only the slice dated inside the coming week</small>
        </div>
      </div>

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

      {!!cash?.recurring?.length && (
        <div className="db-card">
          <h3 className="db-card-title">Recurring discrepancies</h3>
          {cash.recurring.slice(0, 4).map((item) => (
            <p key={item.bucket}>{item.message}</p>
          ))}
        </div>
      )}

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

      <div className="db-card">
        <h3 className="db-card-title">7-day settlement forecast</h3>
        <div className="db-forecast-list">
          {(cash?.forecast || []).map((day) => (
            <div className="db-forecast-row" key={day.date}>
              <span className="db-forecast-label">
                <span className="db-forecast-label-full">{day.label}</span>
                <span className="db-forecast-label-short">{String(day.label || '').slice(0, 3)}</span>
              </span>
              <div className="db-forecast-bar-track">
                <div className="db-forecast-bar" style={{ width: `${(day.expected_inflow_rupees / maxInflow) * 100}%` }} />
              </div>
              <strong>{formatRupees(day.expected_inflow_rupees)}</strong>
              <span className="text-dim">{day.payments_due} due · {day.exceptions_due} blocked</span>
            </div>
          ))}
        </div>
      </div>

      <div className="db-report-grid">
        <div className="db-card">
          <h3 className="db-card-title">Three-way match</h3>
          <p className="db-card-sub">Payments vs settlements vs expected bank credit</p>
          <div className="db-source-grid">
            <div>
              <span>Payments ledger</span>
              <strong>{sources?.payments.count || 0} rows</strong>
              <small>{formatRupees(sources?.payments.gmv_rupees)} GMV</small>
            </div>
            <div>
              <span>Settlements</span>
              <strong>{sources?.settlements.count || 0} UTRs</strong>
              <small>{formatRupees(sources?.settlements.credited_rupees)} credited · {sources?.settlements.missing || 0} missing</small>
            </div>
            <div>
              <span>Expected bank</span>
              <strong>{formatRupees(sources?.expected_bank.expected_rupees)}</strong>
              <small>{sources?.three_way_matches || 0} three-way matches</small>
            </div>
          </div>
        </div>
        <div className="db-card">
          <h3 className="db-card-title">GST tax-line matcher</h3>
          <p className="db-card-sub">18% GST is on the Razorpay fee, not on GMV</p>
          <div className="db-source-grid">
            <div>
              <span>Expected GST</span>
              <strong>{formatRupees(taxLines?.expected_gst_rupees)}</strong>
            </div>
            <div>
              <span>Actual GST</span>
              <strong>{formatRupees(taxLines?.actual_gst_rupees)}</strong>
            </div>
            <div>
              <span>Breaks</span>
              <strong>{taxLines?.mismatched_lines || 0}</strong>
              <small>{taxLines?.matched_lines || 0} lines in tolerance</small>
            </div>
          </div>
        </div>
      </div>

      <div className="db-card">
        <h3 className="db-card-title">GST lines that need a look</h3>
        <table className="db-table mobile-cards">
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
            {(taxLines?.lines || []).slice(0, 12).map((line) => (
              <tr key={line.payment_id}>
                <td data-label="Payment ID" className="db-exc-id">{line.payment_id}</td>
                <td data-label="Fee">{formatRupees(line.fee_rupees)}</td>
                <td data-label="Expected GST">{formatRupees(line.expected_gst_rupees)}</td>
                <td data-label="Actual GST">{formatRupees(line.actual_gst_rupees)}</td>
                <td data-label="Status"><span className={`db-status-badge ${line.status === 'matched' ? 'db-status-reconciled' : 'db-status-pending'}`}>{line.status}</span></td>
              </tr>
            ))}
            {!(taxLines?.lines || []).length && (
              <tr><td colSpan="5" className="db-table-empty">Every GST line matches 18% of fee.</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {closeReport && (
        <div className="db-card">
          <h3 className="db-card-title">Last close — exceptions the agent would not invent</h3>
          <table className="db-table mobile-cards">
            <thead>
              <tr>
                <th>Payment ID</th>
                <th>Type</th>
                <th>Why it stayed</th>
              </tr>
            </thead>
            <tbody>
              {closeReport.remaining_exceptions.map((item) => (
                <tr key={item.payment_id}>
                  <td data-label="Payment ID" className="db-exc-id">{item.payment_id}</td>
                  <td data-label="Type"><ExceptionBadge type={item.mismatch_type} /></td>
                  <td data-label="Why it stayed">{item.suggested_action?.detail || item.explanation}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function AuditPage() {
  const {
    auditSearch, setAuditSearch, visibleAuditLogs,
    auditPage, setAuditPage, totalAuditPages,
    auditFilter, setAuditFilter, auditSource, setAuditSource, auditActionType, setAuditActionType,
    setDashPage, setSelectedExcId,
  } = useApp();
  const { t } = useLanguage();
  const [openId, setOpenId] = React.useState(null);

  const actorLabel = (log) => {
    if (log.source === 'gemini_api') return 'Gemini';
    if (log.source === 'razorpay_test_api') return 'Razorpay test';
    if (log.source === 'ecommerce_demo') return 'Store demo';
    if (log.source === 'ops_controller' || log.actor === 'finance_ops') return 'Controller';
    return log.actor || 'Rule engine';
  };

  return (
    <div className="db-page">
      <div className="db-page-heading">
        <div>
          <p className="bank-kicker">Immutable trail</p>
          <h2 className="db-page-title">{t('pages.auditTitle')}</h2>
          <p className="db-page-sub">Every engine match, human decision and Gemini answer is stored here. Rows are never rewritten — new actions append.</p>
        </div>
      </div>
      <div className="db-card" data-tour="audit-filters">
        <h3 className="db-card-title">Find an event</h3>
        <MobileFilterPack label="Filters">
          <DateRangeFilter value={auditFilter} onChange={setAuditFilter} mobileSheet={false} />
          <div className="db-exc-filters">
            <input className="db-audit-search" value={auditSearch} onChange={(event) => setAuditSearch(event.target.value)} placeholder="Search payment IDs, actions, or text…" />
            <select className="db-filter-select" value={auditSource} onChange={(event) => setAuditSource(event.target.value)}>
              <option value="all">All actors</option>
              <option value="human">Human / controller</option>
              <option value="ai">Gemini</option>
              <option value="rule_engine">Rule engine</option>
              <option value="razorpay_test_api">Razorpay test</option>
            </select>
            <select className="db-filter-select" value={auditActionType} onChange={(event) => setAuditActionType(event.target.value)}>
              <option value="all">All actions</option>
              <option value="exception">Exception</option>
              <option value="match">Match</option>
              <option value="apply_fix">Apply fix</option>
              <option value="escalate">Escalate</option>
              <option value="investigate">Investigate</option>
              <option value="withdrawal">Withdrawal</option>
              <option value="chat_query">Chat</option>
            </select>
          </div>
        </MobileFilterPack>
        <div className="db-audit-legend-row">
          <span className="db-legend-dot db-legend-engine" /> Rule engine / human
          <span className="db-legend-dot db-legend-razorpay" style={{ marginLeft: 16 }} /> Razorpay test
          <span className="db-legend-dot db-legend-ai" style={{ marginLeft: 16 }} /> Gemini
        </div>
      </div>
      <div className="audit-feed" data-tour="audit-table">
        {visibleAuditLogs.length ? visibleAuditLogs.map((log) => {
          const isAI = log.source === 'gemini_api';
          const isRazorpay = log.source === 'razorpay_test_api';
          const record = String(log.record_ids || '').split(',')[0].trim();
          const open = openId === log.id;
          return (
            <article key={log.id} className={`audit-card ${open ? 'is-open' : ''} ${isAI ? 'is-ai' : ''} ${isRazorpay ? 'is-razorpay' : ''}`}>
              <button type="button" className="audit-card-main" onClick={() => setOpenId(open ? null : log.id)}>
                <time>{formatTimestamp(log.timestamp)}</time>
                <span className={`audit-actor ${isAI ? 'ai' : isRazorpay ? 'razorpay' : 'engine'}`}>{actorLabel(log)}</span>
                <div className="audit-copy">
                  <strong>{titleCaseType(log.action_type)}</strong>
                  <p>{(log.details || '').length > 140 ? `${log.details.slice(0, 140)}…` : (log.details || 'No detail stored.')}</p>
                </div>
                {record ? <code className="db-target-id">{record}</code> : <span className="text-dim">—</span>}
              </button>
              {open && (
                <div className="audit-card-detail">
                  <p>{log.details}</p>
                  {(log.previous_state || log.new_state) && (
                    <p className="text-dim">State {log.previous_state || '—'} → {log.new_state || '—'}</p>
                  )}
                  {record.startsWith('pay_') && (
                    <button
                      type="button"
                      className="db-text-link"
                      onClick={() => {
                        setSelectedExcId(record);
                        setDashPage('exceptions');
                      }}
                    >
                      Open {record} in Exceptions
                    </button>
                  )}
                  {record.startsWith('wd_') && (
                    <button type="button" className="db-text-link" onClick={() => setDashPage('withdraw')}>
                      Open withdrawals
                    </button>
                  )}
                </div>
              )}
            </article>
          );
        }) : (
          <div className="db-card"><p className="db-table-empty">No audit logs recorded yet. Run reconciliation or resolve an exception to see the trail.</p></div>
        )}
      </div>
      <Pagination
        page={auditPage}
        total={totalAuditPages}
        onPrev={() => setAuditPage((page) => Math.max(1, page - 1))}
        onNext={() => setAuditPage((page) => Math.min(totalAuditPages, page + 1))}
      />
    </div>
  );
}

function ControllerPerformance() {
  const [perf, setPerf] = React.useState(null);
  React.useEffect(() => {
    api.performance().then(setPerf).catch(() => setPerf(null));
  }, []);
  if (!perf) return null;
  return (
    <div className="db-card">
      <h3 className="db-card-title">AI vs human</h3>
      <div className="db-stats-row">
        <div className="db-stat-card"><span className="db-stat-label">Auto matched</span><div className="db-stat-value">{perf.automatically_matched}</div></div>
        <div className="db-stat-card"><span className="db-stat-label">Auto resolved</span><div className="db-stat-value">{perf.automatically_resolved}</div></div>
        <div className="db-stat-card"><span className="db-stat-label">Human reviewed</span><div className="db-stat-value">{perf.human_reviewed}</div></div>
        <div className="db-stat-card"><span className="db-stat-label">AI declined</span><div className="db-stat-value">{perf.cases_ai_refused}</div></div>
      </div>
      <p className="text-dim">{perf.note}</p>
    </div>
  );
}

function formatPeriodLabel(label) {
  if (/^\d{4}-\d{2}$/.test(label)) {
    const [year, month] = label.split('-');
    return new Date(Number(year), Number(month) - 1).toLocaleString('en-IN', { month: 'short', year: 'numeric' });
  }
  return label;
}

function EarningsBarChart({ rows, valueKey = 'gross', color = '#0d4fff', empty = 'No earnings in this view.' }) {
  if (!rows?.length) return <p className="db-table-empty">{empty}</p>;
  const max = Math.max(1, ...rows.map((row) => Number(row[valueKey] || 0)));
  return (
    <div className="earn-chart" role="img" aria-label="Earnings bar chart">
      {rows.map((row) => {
        const value = Number(row[valueKey] || 0);
        const pct = Math.max(value > 0 ? 6 : 0, (value / max) * 100);
        return (
          <div className="earn-chart-col" key={row.label}>
            <span className="earn-chart-value">{formatCompactRupees(value)}</span>
            <div className="earn-chart-track">
              <div className="earn-chart-bar" style={{ height: `${pct}%`, background: color }} />
            </div>
            <span className="earn-chart-label">{formatPeriodLabel(row.label)}</span>
            {row.orders != null && <small>{row.orders} orders</small>}
          </div>
        );
      })}
    </div>
  );
}

function GroupedEarningsChart({ rows }) {
  if (!rows?.length) return <p className="db-table-empty">No period series yet.</p>;
  const max = Math.max(1, ...rows.flatMap((row) => [row.gross, row.net, row.tax].map((value) => Number(value || 0))));
  return (
    <div className="earn-chart earn-chart-grouped" role="img" aria-label="GMV, GST and net by period">
      {rows.map((row) => (
        <div className="earn-chart-col" key={row.label}>
          <div className="earn-group-bars">
            {[
              { key: 'gross', color: '#0d4fff', value: row.gross },
              { key: 'tax', color: '#0C2651', value: row.tax },
              { key: 'net', color: '#059669', value: row.net },
            ].map((bar) => (
              <div
                key={bar.key}
                className="earn-group-bar"
                style={{ height: `${Math.max(Number(bar.value) > 0 ? 6 : 0, (Number(bar.value || 0) / max) * 100)}%`, background: bar.color }}
                title={`${bar.key} ${formatRupees(bar.value)}`}
              />
            ))}
          </div>
          <span className="earn-chart-label">{formatPeriodLabel(row.label)}</span>
        </div>
      ))}
    </div>
  );
}

function CompositionBars({ items }) {
  const max = Math.max(1, ...items.map((item) => Number(item.value || 0)));
  return (
    <div className="earn-compose">
      {items.map((item) => (
        <div className="earn-compose-row" key={item.label}>
          <span>{item.label}</span>
          <div className="earn-compose-track">
            <div className="earn-compose-fill" style={{ width: `${(Number(item.value || 0) / max) * 100}%`, background: item.color }} />
          </div>
          <strong>{formatRupees(item.value)}</strong>
        </div>
      ))}
    </div>
  );
}

function ReportsPage() {
  const { batchLoaded, reconciliationRun, analytics, metrics, handleLoadBatch, handleRunReconciliation, isConnected, downloadWordReport } = useApp();
  const { t } = useLanguage();
  const [period, setPeriod] = React.useState('overall');

  return (
    <div className="db-page">
      <div className="db-page-heading">
        <div>
          <h2 className="db-page-title">{t('pages.reportsTitle')}</h2>
          <p className="db-page-sub">Earning analysis from the active batch — overall, monthly and yearly. Live figures, not a placeholder.</p>
        </div>
        {reconciliationRun && (
          <button className="db-topbar-cta sticky-page-cta" type="button" onClick={downloadWordReport}>
            Download Word close report
          </button>
        )}
      </div>
      {reconciliationRun && <ControllerPerformance />}
      {!batchLoaded || !reconciliationRun ? (
        <div className="db-card db-reports-empty-state">
          <div className="db-reports-empty-header">
            <h3>Load a batch to see the books</h3>
          </div>
          <button
            className="db-topbar-cta"
            type="button"
            onClick={async () => {
              if (!batchLoaded) {
                const loaded = await handleLoadBatch();
                if (!loaded) return;
              }
              await handleRunReconciliation({ force: true });
            }}
            disabled={!isConnected}
          >
            Load & reconcile
          </button>
        </div>
      ) : analytics ? (
        <div className="db-reports-shell">
          <div className="earn-period-tabs" role="tablist" aria-label="Earning analysis period" data-tour="reports-period">
            {[
              { id: 'overall', label: 'Overall' },
              { id: 'monthly', label: 'Monthly' },
              { id: 'yearly', label: 'Yearly' },
            ].map((tab) => (
              <button
                key={tab.id}
                type="button"
                role="tab"
                aria-selected={period === tab.id}
                className={period === tab.id ? 'active' : ''}
                onClick={() => setPeriod(tab.id)}
              >
                {tab.label}
              </button>
            ))}
          </div>
          <div className="db-reports-summary-row">
            <div className="db-report-highlight-card db-report-highlight-blue"><span className="db-report-kicker">Orders</span><strong>{analytics.total_orders}</strong></div>
            <div className="db-report-highlight-card db-report-highlight-green"><span className="db-report-kicker">GMV</span><strong>{formatRupees(analytics.total_earnings)}</strong></div>
            <div className="db-report-highlight-card db-report-highlight-violet"><span className="db-report-kicker">GST collected</span><strong>{formatRupees(analytics.total_tax)}</strong></div>
            <div className="db-report-highlight-card db-report-highlight-amber"><span className="db-report-kicker">Net settlement</span><strong>{formatRupees(analytics.net_settlement)}</strong></div>
          </div>
          {period === 'overall' && (
            <div className="db-report-grid">
              <div className="db-card db-report-panel">
                <h3 className="db-card-title">Earnings mix</h3>
                <CompositionBars items={[
                  { label: 'GMV', value: analytics.total_earnings, color: '#0d4fff' },
                  { label: 'Net settlement', value: analytics.net_settlement, color: '#059669' },
                  { label: 'GST collected', value: analytics.total_tax, color: '#0C2651' },
                  { label: 'Fees', value: analytics.total_fees, color: '#f59e0b' },
                  { label: 'Refunds', value: analytics.total_refunds, color: '#ef4444' },
                ]} />
              </div>
              <div className="db-card db-report-panel">
                <h3 className="db-card-title">GMV vs net by month</h3>
                <GroupedEarningsChart rows={analytics.monthly} />
                <div className="earn-legend">
                  <span><i style={{ background: '#0d4fff' }} /> GMV</span>
                  <span><i style={{ background: '#0C2651' }} /> GST</span>
                  <span><i style={{ background: '#059669' }} /> Net</span>
                </div>
              </div>
            </div>
          )}
          {period === 'monthly' && (
            <div className="db-card db-report-panel">
              <div className="db-report-panel-header">
                <h3 className="db-card-title">Monthly earnings</h3>
                <span className="db-report-chip">{analytics.monthly.length} months</span>
              </div>
              <EarningsBarChart rows={analytics.monthly} valueKey="gross" />
              <div className="earn-legend">
                <span><i style={{ background: '#0d4fff' }} /> GMV</span>
              </div>
              <GroupedEarningsChart rows={analytics.monthly} />
              <div className="db-analytics-list">
                {analytics.monthly.map((item) => (
                  <div className="db-analytics-row" key={item.label}>
                    <div className="db-analytics-title"><strong>{formatPeriodLabel(item.label)}</strong><span>{item.orders} orders</span></div>
                    <div className="db-analytics-stats">
                      <span className="db-analytics-pill db-analytics-pill-blue">GMV {formatRupees(item.gross)}</span>
                      <span className="db-analytics-pill db-analytics-pill-violet">GST {formatRupees(item.tax)}</span>
                      <span className="db-analytics-pill db-analytics-pill-green">Net {formatRupees(item.net)}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
          {period === 'yearly' && (
            <div className="db-card db-report-panel">
              <div className="db-report-panel-header">
                <h3 className="db-card-title">Yearly earnings</h3>
                <span className="db-report-chip">{analytics.yearly.length} year{analytics.yearly.length === 1 ? '' : 's'}</span>
              </div>
              <EarningsBarChart rows={analytics.yearly} valueKey="gross" color="#059669" />
              <GroupedEarningsChart rows={analytics.yearly} />
              <div className="db-analytics-list">
                {analytics.yearly.map((item) => (
                  <div className="db-analytics-row" key={item.label}>
                    <div className="db-analytics-title"><strong>{item.label}</strong><span>{item.orders} orders</span></div>
                    <div className="db-analytics-stats">
                      <span className="db-analytics-pill db-analytics-pill-blue">GMV {formatRupees(item.gross)}</span>
                      <span className="db-analytics-pill db-analytics-pill-orange">Fees {formatRupees(item.fees)}</span>
                      <span className="db-analytics-pill db-analytics-pill-red">Refunds {formatRupees(item.refunds)}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
          <div className="db-card db-report-panel">
            <h3 className="db-card-title">Engine validation</h3>
            <div className="db-reports-metrics">
              <div className="db-card db-report-metric"><span className="db-stat-label">Seeded</span><div className="db-stat-value">{metrics?.validation?.seeded_mismatches ?? '—'}</div></div>
              <div className="db-card db-report-metric"><span className="db-stat-label">Detected</span><div className="db-stat-value" style={{ color: '#10b981' }}>{metrics?.validation ? `${metrics.validation.correctly_detected} (${(metrics.validation.detection_rate * 100).toFixed(0)}%)` : '—'}</div></div>
              <div className="db-card db-report-metric"><span className="db-stat-label">False positives</span><div className="db-stat-value" style={{ color: '#ef4444' }}>{metrics?.validation?.false_positives ?? '—'}</div></div>
              <div className="db-card db-report-metric"><span className="db-stat-label">Precision</span><div className="db-stat-value">{metrics?.validation?.precision != null ? `${(metrics.validation.precision * 100).toFixed(0)}%` : '—'}</div></div>
              <div className="db-card db-report-metric"><span className="db-stat-label">Recall</span><div className="db-stat-value">{metrics?.validation?.recall != null ? `${(metrics.validation.recall * 100).toFixed(0)}%` : '—'}</div></div>
              <div className="db-card db-report-metric"><span className="db-stat-label">Throughput</span><div className="db-stat-value">{metrics?.records_per_second != null ? `${metrics.records_per_second}/s` : '—'}</div></div>
              <div className="db-card db-report-metric"><span className="db-stat-label">Reconcile time</span><div className="db-stat-value">{metrics?.processing_time_seconds != null ? `${Number(metrics.processing_time_seconds).toFixed(3)}s` : '—'}</div></div>
            </div>
          </div>
        </div>
      ) : (
        <div className="db-card"><p className="db-table-empty">Analytics unavailable.</p></div>
      )}
    </div>
  );
}

export default function Dashboard() {
  const {
    dashPage, setDashPage, setActiveTab, sidebarOpen, setSidebarOpen,
    isConnected, reconciliationRun, closingBooks, handleCloseBooks,
    metrics, setSelectedExcId,
  } = useApp();
  const { openChooser } = useTour();
  const { t } = useLanguage();

  const openExceptions = metrics?.unresolved_exceptions ?? metrics?.exceptions ?? 0;
  const matchLabel = reconciliationRun ? matchPercent(metrics) : t('chrome.noBatch');
  const matchWidth = reconciliationRun ? Math.round((metrics?.match_rate || 0) * 100) : 0;
  const navGroups = [
    {
      label: t('nav.control'),
      items: [
        { id: 'home', label: t('nav.home') },
        { id: 'chat', label: t('nav.chat') },
        { id: 'guide', label: t('nav.guide') },
      ],
    },
    {
      label: t('nav.operations'),
      items: [
        { id: 'payments', label: t('nav.payments') },
        { id: 'reconciliation', label: t('nav.reconciliation') },
        { id: 'exceptions', label: t('nav.exceptions'), count: openExceptions },
      ],
    },
    {
      label: t('nav.finance'),
      items: [
        { id: 'cash', label: t('nav.cash') },
        { id: 'gst', label: t('nav.gst') },
        { id: 'withdraw', label: t('nav.withdraw') },
      ],
    },
    {
      label: t('nav.records'),
      items: [
        { id: 'audit', label: t('nav.audit') },
        { id: 'knowledge', label: t('nav.knowledge') },
        { id: 'reports', label: t('nav.reports') },
      ],
    },
  ];

  return (
    <div className="db-shell">
      {sidebarOpen ? (
        <button className="db-sidebar-scrim" type="button" aria-label="Close menu" onClick={() => setSidebarOpen(false)} />
      ) : null}
      <aside className={`db-sidebar ${sidebarOpen ? 'open' : ''}`}>
        <div className="db-sidebar-brand">
          <button className="logo" onClick={() => setActiveTab('overview')} type="button" style={{ border: 'none', background: 'none', padding: 0, cursor: 'pointer' }}>
            <span className="logo-accent">Razor-AI</span>
          </button>
          <span className="db-sidebar-subtitle">{t('chrome.subtitle')}</span>
        </div>
        <div className="db-sidebar-progress">
          <span>{t('chrome.batchProgress')}</span>
          <strong>{matchLabel}{reconciliationRun && openExceptions ? ` · ${t('chrome.open', { count: openExceptions })}` : ''}</strong>
          <div className="db-sidebar-progress-track" aria-hidden="true">
            <div className="db-sidebar-progress-fill" style={{ width: `${matchWidth}%` }} />
          </div>
        </div>
        <nav className="db-sidebar-nav">
          {navGroups.map((group) => (
            <div className="db-nav-group" key={group.label}>
              <div className="db-nav-group-label">{group.label}</div>
              {group.items.map((item) => (
                <button
                  key={item.id}
                  className={`db-nav-item ${dashPage === item.id ? 'active' : ''}`}
                  onClick={() => {
                    if (item.id === 'exceptions') setSelectedExcId(null);
                    setDashPage(item.id);
                    setSidebarOpen(false);
                  }}
                  type="button"
                >
                  <span className="db-nav-label">{item.label}</span>
                  {item.count > 0 ? <span className="db-nav-count">{item.count}</span> : null}
                </button>
              ))}
            </div>
          ))}
        </nav>
      </aside>
      <div className="db-main">
        <header className="db-topbar">
          <div className="db-topbar-left">
            <button className="db-sidebar-toggle" onClick={() => setSidebarOpen((open) => !open)} type="button">{t('chrome.menu')}</button>
            <span className="db-topbar-divider" />
            <span className="db-topbar-label">{t('chrome.subtitle')}</span>
            <span className={`db-conn-pill ${isConnected ? 'online' : 'offline'}`}>{isConnected ? t('chrome.engineLive') : t('chrome.offline')}</span>
          </div>
          <div className="db-topbar-right">
            <div className="db-topbar-actions">
              <LanguageToggle compact />
              <button className="db-quick-link" onClick={openChooser} type="button">{t('chrome.tour')}</button>
              <button className="db-topbar-cta" onClick={handleCloseBooks} disabled={!isConnected || closingBooks} type="button">
                {closingBooks ? t('chrome.closing') : (reconciliationRun ? t('chrome.closeBooks') : t('chrome.loadClose'))}
              </button>
              <NotificationMenu />
            </div>
          </div>
        </header>
        <div className="db-content">
          {dashPage === 'home' && <HomePage />}
          {dashPage === 'chat' && <ChatPage />}
          {dashPage === 'payments' && <PaymentsPage />}
          {dashPage === 'reconciliation' && <ReconciliationPage />}
          {dashPage === 'exceptions' && <ExceptionsPage />}
          {dashPage === 'cash' && <CashPositionPage />}
          {dashPage === 'gst' && <GstPage />}
          {dashPage === 'withdraw' && <WithdrawPage />}
          {dashPage === 'audit' && <AuditPage />}
          {dashPage === 'knowledge' && <KnowledgePage />}
          {dashPage === 'guide' && <GuidePage />}
          {dashPage === 'reports' && <ReportsPage />}
        </div>
      </div>
    </div>
  );
}
