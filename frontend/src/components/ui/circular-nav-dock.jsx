import React, { useCallback, useEffect, useRef, useState } from 'react';
import { BarChart3, FileSpreadsheet, Home, Menu, Store, User, X } from 'lucide-react';
import CircularNavigation, { layoutFan, placePanel } from './circular-navigation-bar';
import { useApp } from '../../AppContext';
import { api } from '../../lib/api';
import { downloadBlob, formatDayLabel, formatPaise, formatRupees, titleCaseType } from '../../lib/format';

const FAB = 60;
const EDGE = 20;
const SNAP = 28;
const DRAG_THRESHOLD = 8;
const STORAGE_KEY = 'razorai.circNav.pos';

function todayStamp() {
  const now = new Date();
  const month = String(now.getMonth() + 1).padStart(2, '0');
  const day = String(now.getDate()).padStart(2, '0');
  return `${now.getFullYear()}-${month}-${day}`;
}

function viewportSize() {
  return { width: window.innerWidth, height: window.innerHeight };
}

function defaultPos() {
  const { width, height } = viewportSize();
  return { x: width - FAB - EDGE, y: height - FAB - EDGE };
}

function clampPos(x, y, view = viewportSize()) {
  return {
    x: Math.min(Math.max(EDGE, x), Math.max(EDGE, view.width - FAB - EDGE)),
    y: Math.min(Math.max(EDGE, y), Math.max(EDGE, view.height - FAB - EDGE)),
  };
}

function snapPos(x, y, view = viewportSize()) {
  const maxX = view.width - FAB - EDGE;
  const maxY = view.height - FAB - EDGE;
  let nextX = x;
  let nextY = y;
  if (x < EDGE + SNAP) nextX = EDGE;
  else if (x > maxX - SNAP) nextX = maxX;
  if (y < EDGE + SNAP) nextY = EDGE;
  else if (y > maxY - SNAP) nextY = maxY;
  return clampPos(nextX, nextY, view);
}

function readSavedPos() {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return defaultPos();
    const parsed = JSON.parse(raw);
    if (!Number.isFinite(parsed?.x) || !Number.isFinite(parsed?.y)) return defaultPos();
    return clampPos(parsed.x, parsed.y);
  } catch {
    return defaultPos();
  }
}

function savePos(pos) {
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(pos));
  } catch {
    /* session-only; ignore quota */
  }
}

function radialRadius(view) {
  const shortest = Math.min(view.width, view.height);
  if (shortest < 480) return 72;
  if (shortest < 768) return 80;
  return 88;
}

export default function CircularNavDock() {
  const {
    setActiveTab, setMerchantView, setDashPage, setSelectedExcId, setProfileMenuOpen,
    handleSuggestedClick, downloadCsvReport, downloadWordReport, downloadAnalysisReport, handleResetDemo,
    reconciliationRun, isConnected, triggerToast, metrics, dashPage, activeTab,
    paymentFilter, setInquiryDate,
  } = useApp();
  const [isOpen, setIsOpen] = useState(false);
  const [panel, setPanel] = useState(null);
  const [date, setDate] = useState(todayStamp());
  const [paymentId, setPaymentId] = useState('');
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(false);
  const [sheetBusy, setSheetBusy] = useState(false);
  const [pos, setPos] = useState(defaultPos);
  const [viewport, setViewport] = useState(viewportSize);
  const dragRef = useRef({
    active: false,
    moved: false,
    pointerId: null,
    startX: 0,
    startY: 0,
    origX: 0,
    origY: 0,
  });

  useEffect(() => {
    setPos(readSavedPos());
  }, []);

  useEffect(() => {
    if (paymentFilter?.preset === 'custom' && paymentFilter.start) {
      setDate(paymentFilter.start);
      setInquiryDate(paymentFilter.start);
    }
  }, [paymentFilter, setInquiryDate]);

  useEffect(() => {
    const onResize = () => {
      const view = viewportSize();
      setViewport(view);
      setPos((current) => {
        const next = clampPos(current.x, current.y, view);
        savePos(next);
        return next;
      });
    };
    window.addEventListener('resize', onResize);
    window.visualViewport?.addEventListener('resize', onResize);
    return () => {
      window.removeEventListener('resize', onResize);
      window.visualViewport?.removeEventListener('resize', onResize);
    };
  }, []);

  useEffect(() => {
    if (!isOpen && !panel) return undefined;
    const onKey = (event) => {
      if (event.key === 'Escape') {
        setIsOpen(false);
        setPanel(null);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [isOpen, panel]);

  const onPointerDown = (event) => {
    if (event.button != null && event.button !== 0) return;
    event.preventDefault();
    event.currentTarget.setPointerCapture(event.pointerId);
    dragRef.current = {
      active: true,
      moved: false,
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      origX: pos.x,
      origY: pos.y,
    };
  };

  const onPointerMove = (event) => {
    const drag = dragRef.current;
    if (!drag.active || drag.pointerId !== event.pointerId) return;
    const dx = event.clientX - drag.startX;
    const dy = event.clientY - drag.startY;
    if (!drag.moved && Math.hypot(dx, dy) < DRAG_THRESHOLD) return;
    drag.moved = true;
    setPos(clampPos(drag.origX + dx, drag.origY + dy));
  };

  const onPointerUp = (event) => {
    const drag = dragRef.current;
    if (!drag.active || drag.pointerId !== event.pointerId) return;
    drag.active = false;
    try {
      event.currentTarget.releasePointerCapture(event.pointerId);
    } catch {
      /* already released */
    }
    if (drag.moved) {
      setPos((current) => {
        const snapped = snapPos(current.x, current.y);
        savePos(snapped);
        return snapped;
      });
      return;
    }
    setIsOpen((open) => !open);
  };

  const loadSummary = async (stamp = date, pay = paymentId) => {
    if (!reconciliationRun) {
      triggerToast('Reconcile a batch first.', 'warning');
      return;
    }
    setLoading(true);
    try {
      const data = await api.daySummary(stamp, pay.trim());
      let payload = data;
      if ((!stamp || data.totals?.count === 0) && data.latest_date && data.latest_date !== stamp && !pay.trim()) {
        payload = await api.daySummary(data.latest_date, '');
      }
      setSummary(payload);
      const used = payload.date || payload.latest_date || stamp;
      if (used) {
        setDate(used);
        setInquiryDate(used);
      }
    } catch (error) {
      triggerToast(error.message || 'Could not load the daily brief.', 'warning');
    } finally {
      setLoading(false);
    }
  };

  const downloadSheet = async () => {
    if (!reconciliationRun) {
      triggerToast('Reconcile a batch first.', 'warning');
      return;
    }
    setSheetBusy(true);
    try {
      const blob = await api.excelReport(date);
      downloadBlob(blob, `razorai-${date || 'day'}.xlsx`, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
      triggerToast('Spreadsheet downloaded. Open it in Excel or upload to Google Sheets.', 'success');
      setPanel(null);
    } catch (error) {
      triggerToast(error.message || 'No rows for that date.', 'warning');
    } finally {
      setSheetBusy(false);
    }
  };

  const onHome = activeTab === 'dashboard' && dashPage === 'home' && !panel;
  const onStore = activeTab === 'merchant-checkout' && !panel;
  const navItems = [
    {
      name: 'Home',
      icon: Home,
      active: onHome,
      onSelect: () => { setPanel(null); setActiveTab('dashboard'); setDashPage('home'); },
    },
    {
      name: 'Account',
      icon: User,
      active: panel === 'account',
      onSelect: () => { setPanel('account'); setProfileMenuOpen(false); },
    },
    {
      name: 'Summary',
      icon: BarChart3,
      active: panel === 'summary',
      onSelect: () => {
        const stamp = paymentFilter?.preset === 'custom' && paymentFilter.start ? paymentFilter.start : date;
        setPanel('summary');
        loadSummary(stamp, '');
      },
    },
    {
      name: 'Store',
      icon: Store,
      active: onStore,
      onSelect: () => { setPanel(null); setMerchantView('store'); setActiveTab('merchant-checkout'); },
    },
    {
      name: 'Sheets',
      icon: FileSpreadsheet,
      active: panel === 'sheet',
      onSelect: () => {
        setPanel('sheet');
        if (!reconciliationRun) return;
        api.daySummary(date, '').then((data) => {
          if ((!date || !data.totals?.count) && data.latest_date) {
            setDate(data.latest_date);
            setInquiryDate(data.latest_date);
          }
        }).catch(() => {});
      },
    },
  ];

  const handleSelect = useCallback((item) => {
    setIsOpen(false);
    item.onSelect?.();
  }, []);

  const radius = radialRadius(viewport);
  const spots = layoutFan(navItems.length, radius, FAB, pos, viewport);
  const panelBox = placePanel(pos, viewport, FAB);
  const headline = summary?.headline || (
    summary
      ? `Summary for ${formatDayLabel(summary.date || summary.latest_date || date)} · Batch ${summary.batch_id || metrics?.batch?.batch_id || '—'}`
      : ''
  );

  return (
    <>
      {isOpen ? (
        <button
          className="circ-nav-scrim"
          type="button"
          aria-label="Close menu"
          onClick={() => setIsOpen(false)}
        />
      ) : null}

      <div
        className={`circ-nav-root ${isOpen ? 'is-open' : ''}${dragRef.current.moved ? ' is-dragging' : ''}`}
        style={{ left: pos.x, top: pos.y }}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
      >
        <CircularNavigation
          navItems={navItems}
          isOpen={isOpen}
          fabSize={FAB}
          spots={spots}
          onSelect={handleSelect}
        />
        <button
          type="button"
          className="circ-nav-fab"
          aria-expanded={isOpen}
          aria-label={isOpen ? 'Close menu' : 'Open menu. Drag to move.'}
        >
          {isOpen ? <X className="circ-nav-fab-icon" /> : <Menu className="circ-nav-fab-icon" />}
        </button>
      </div>

      {panel && (
        <div className="circ-panel-overlay" role="presentation">
          <button className="circ-nav-backdrop" type="button" aria-label="Close panel" onClick={() => setPanel(null)} />
          <div
            className="circ-panel"
            role="dialog"
            aria-modal="true"
            style={{
              left: panelBox.left,
              top: panelBox.top,
              width: panelBox.width,
              maxHeight: panelBox.maxHeight,
            }}
          >
            {panel === 'summary' && (
              <>
                <header className="circ-panel-head">
                  <div>
                    <h3>Daily brief</h3>
                    <p className="circ-scope-line">{headline || 'Pick a day from this batch. Figures come from reconciled records, not the model.'}</p>
                  </div>
                  <button type="button" className="db-text-link" onClick={() => setPanel(null)}>Close</button>
                </header>
                <form
                  className="circ-panel-form"
                  onSubmit={(event) => {
                    event.preventDefault();
                    loadSummary(date, paymentId);
                  }}
                >
                  <label>
                    Date
                    <input type="date" value={date} onChange={(event) => setDate(event.target.value)} />
                  </label>
                  <label>
                    Payment ID (optional)
                    <input
                      value={paymentId}
                      onChange={(event) => setPaymentId(event.target.value)}
                      placeholder="pay_…"
                    />
                  </label>
                  <button className="db-topbar-cta" type="submit" disabled={!isConnected || loading}>
                    {loading ? 'Loading…' : 'Show brief'}
                  </button>
                </form>
                {summary && (
                  <div className="circ-panel-body">
                    <p className="circ-scope-line">{headline}</p>
                    <p className="text-dim">{summary.totals?.count ? `${summary.totals.count} payments in this slice.` : `No captures on ${formatDayLabel(summary.date || summary.label)}.${summary.latest_date ? ` Latest in batch: ${formatDayLabel(summary.latest_date)}.` : ''}`}</p>
                    <div className="circ-kpi-row">
                      <div><span>GMV</span><strong>{formatRupees(summary.totals?.gmv_rupees)}</strong></div>
                      <div><span>Matched</span><strong>{summary.totals?.matched ?? 0}</strong></div>
                      <div><span>Exceptions</span><strong>{summary.totals?.exceptions ?? 0}</strong></div>
                      <div><span>At risk</span><strong>{formatRupees(summary.totals?.amount_at_risk_rupees)}</strong></div>
                    </div>
                    {!!Object.keys(summary.mismatch_breakdown || {}).length && (
                      <ul className="circ-breakdown">
                        {Object.entries(summary.mismatch_breakdown).map(([key, count]) => (
                          <li key={key}>{titleCaseType(key)} · {count}</li>
                        ))}
                      </ul>
                    )}
                    {summary.payment && (
                      <div className="circ-payment-card">
                        <strong>{summary.payment.payment_id}</strong>
                        <p>{formatPaise(summary.payment.amount)} · {summary.payment.reconciliation_status}{summary.payment.mismatch_type ? ` · ${titleCaseType(summary.payment.mismatch_type)}` : ''}</p>
                        {summary.payment.explanation ? <p>{summary.payment.explanation}</p> : null}
                        <div className="circ-panel-actions">
                          <button
                            type="button"
                            className="db-quick-link"
                            onClick={() => {
                              setActiveTab('dashboard');
                              setSelectedExcId(summary.payment.payment_id);
                              setDashPage(summary.payment.reconciliation_status === 'exception' ? 'exceptions' : 'payments');
                              setPanel(null);
                            }}
                          >
                            Open record
                          </button>
                          <button
                            type="button"
                            className="db-quick-link"
                            onClick={() => {
                              setActiveTab('dashboard');
                              setDashPage('home');
                              handleSuggestedClick(`What happened with ${summary.payment.payment_id}?`);
                              setPanel(null);
                            }}
                          >
                            Ask in Q&A
                          </button>
                        </div>
                      </div>
                    )}
                    {paymentId.trim() && summary.payment_found === false && (
                      <p className="db-ingest-bad">No payment in this batch matches that ID.</p>
                    )}
                    {!!summary.exceptions?.length && (
                      <ul className="circ-exc-list">
                        {summary.exceptions.map((item) => (
                          <li key={item.payment_id}>
                            <button
                              type="button"
                              onClick={() => {
                                setPaymentId(item.payment_id);
                                loadSummary(date, item.payment_id);
                              }}
                            >
                              {item.payment_id} · {titleCaseType(item.mismatch_type)} · {item.priority}
                            </button>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                )}
              </>
            )}
            {panel === 'sheet' && (
              <>
                <header className="circ-panel-head">
                  <div>
                    <h3>Spreadsheet</h3>
                    <p>Excel with colour highlights. Upload the file to Google Sheets if you want it there — this demo does not write to a live Google account.</p>
                  </div>
                  <button type="button" className="db-text-link" onClick={() => setPanel(null)}>Close</button>
                </header>
                <form
                  className="circ-panel-form"
                  onSubmit={(event) => {
                    event.preventDefault();
                    downloadSheet();
                  }}
                >
                  <label>
                    Date
                    <input type="date" value={date} onChange={(event) => setDate(event.target.value)} required />
                  </label>
                  <button className="db-topbar-cta" type="submit" disabled={!isConnected || sheetBusy}>
                    {sheetBusy ? 'Building…' : 'Download spreadsheet'}
                  </button>
                </form>
              </>
            )}
            {panel === 'account' && (
              <>
                <header className="circ-panel-head">
                  <div>
                    <h3>Account</h3>
                    <p>Finance ops · controller@razorpay.demo</p>
                  </div>
                  <button type="button" className="db-text-link" onClick={() => setPanel(null)}>Close</button>
                </header>
                <div className="circ-panel-actions circ-panel-actions-stack">
                  <button type="button" className="db-quick-link" onClick={() => { setActiveTab('dashboard'); setDashPage('cash'); setPanel(null); }}>Cash position</button>
                  <button type="button" className="db-quick-link" onClick={() => { setActiveTab('dashboard'); setSelectedExcId(null); setDashPage('exceptions'); setPanel(null); }}>Exception queue</button>
                  <button type="button" className="db-quick-link" onClick={() => { downloadCsvReport(); setPanel(null); }}>Download CSV</button>
                  <button type="button" className="db-quick-link" onClick={() => { downloadWordReport(); setPanel(null); }}>Download Word report</button>
                  <button type="button" className="db-quick-link" onClick={() => { downloadAnalysisReport(); setPanel(null); }}>Download analysis</button>
                  <button type="button" className="db-quick-link" onClick={() => { handleResetDemo(); setPanel(null); }}>Reset demo</button>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </>
  );
}
