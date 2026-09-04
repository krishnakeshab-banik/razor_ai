import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { api } from './lib/api';
import {
  BATCH_TEMPLATE_CSV,
  CHAT_MESSAGE_LIMIT,
  DASHBOARD_PAGE_SIZE,
  downloadBlob,
  flagDestination,
  initialChatMessage,
  matchPercent,
} from './lib/format';
import { EMPTY_DATE_FILTER, dateQuery } from './components/DateRangeFilter';
import { parseHash, sameHash, toHash } from './lib/routes';
import { loadRazorpayScript, openRazorpayCheckout } from './lib/razorpay';
import { getLocale } from './i18n/LanguageContext';

const AppContext = import.meta.hot?.data?.AppContext ?? createContext(null);
if (import.meta.hot) import.meta.hot.data.AppContext = AppContext;

export function useApp() {
  const value = useContext(AppContext);
  if (!value) throw new Error('useApp must be used inside AppProvider');
  return value;
}

export function AppProvider({ children }) {
  const initialRoute = parseHash(typeof window !== 'undefined' ? window.location.hash : '');
  const [activeTab, setActiveTabState] = useState(initialRoute.activeTab);
  const [dashPage, setDashPageState] = useState(initialRoute.dashPage);
  const [expandedExc, setExpandedExc] = useState(null);
  const [selectedExcId, setSelectedExcId] = useState(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const [isConnected, setIsConnected] = useState(false);
  const [batchLoaded, setBatchLoaded] = useState(false);
  const [reconciliationRun, setReconciliationRun] = useState(false);
  const [sessionReady, setSessionReady] = useState(false);
  const [closingBooks, setClosingBooks] = useState(false);
  const [resolvingId, setResolvingId] = useState(null);

  const [metrics, setMetrics] = useState(null);
  const [analytics, setAnalytics] = useState(null);
  const [exceptions, setExceptions] = useState([]);
  const [cash, setCash] = useState(null);
  const [sources, setSources] = useState(null);
  const [taxLines, setTaxLines] = useState(null);
  const [closeReport, setCloseReport] = useState(null);
  const [investigation, setInvestigation] = useState(null);
  const [difference, setDifference] = useState(null);
  const [whatIfResult, setWhatIfResult] = useState(null);
  const [ingestReport, setIngestReport] = useState(null);

  const [searchQuery, setSearchQuery] = useState('');
  const [auditSearch, setAuditSearch] = useState('');
  const [mismatchFilter, setMismatchFilter] = useState('all');
  const [exceptionPage, setExceptionPage] = useState(1);
  const [auditPage, setAuditPage] = useState(1);
  const [generateCount, setGenerateCount] = useState(100);

  const [chatInput, setChatInput] = useState('');
  const [chatMessages, setChatMessages] = useState([initialChatMessage()]);
  const [chatLoading, setChatLoading] = useState(false);
  const chatBottomRef = useRef(null);
  const batchInputRef = useRef(null);

  const [merchantView, setMerchantViewState] = useState(initialRoute.merchantView);
  const routeRef = useRef(initialRoute);
  const routeQueueRef = useRef({});
  const routeFlushRef = useRef(false);
  const applyingHashRef = useRef(false);
  const [cart, setCart] = useState([]);
  const [lastPayment, setLastPayment] = useState(null);
  const [checkoutForm, setCheckoutForm] = useState({
    cardNumber: '',
    expiry: '',
    cvc: '',
    name: '',
    email: '',
    phone: '',
    address: '',
    city: 'Bengaluru',
    paymentMethod: 'UPI',
    saveCard: true,
    aiOutcome: 'clean',
  });
  const [checkoutBusy, setCheckoutBusy] = useState(false);

  const flushRoute = useCallback(() => {
    routeFlushRef.current = false;
    routeQueueRef.current = {};
    if (applyingHashRef.current) return;
    const hash = toHash(routeRef.current);
    if (!sameHash(window.location.hash, hash)) {
      window.history.pushState(null, '', hash);
    }
  }, []);

  const patchRoute = useCallback((partial) => {
    routeRef.current = { ...routeRef.current, ...partial };
    routeQueueRef.current = { ...routeQueueRef.current, ...partial };
    if (partial.activeTab != null) setActiveTabState(routeRef.current.activeTab);
    if (partial.dashPage != null) setDashPageState(routeRef.current.dashPage);
    if (partial.merchantView != null) setMerchantViewState(routeRef.current.merchantView);
    if (!routeFlushRef.current) {
      routeFlushRef.current = true;
      queueMicrotask(flushRoute);
    }
  }, [flushRoute]);

  const setActiveTab = useCallback((tab) => {
    const next = typeof tab === 'function' ? tab(routeRef.current.activeTab) : tab;
    patchRoute({ activeTab: next });
  }, [patchRoute]);

  const setDashPage = useCallback((page) => {
    const next = typeof page === 'function' ? page(routeRef.current.dashPage) : page;
    patchRoute({ activeTab: 'dashboard', dashPage: next });
  }, [patchRoute]);

  const goToAdmin = useCallback((page = 'home') => {
    applyingHashRef.current = false;
    patchRoute({ activeTab: 'dashboard', dashPage: page });
    const next = toHash({ ...routeRef.current, activeTab: 'dashboard', dashPage: page });
    if (!sameHash(window.location.hash, next)) {
      applyingHashRef.current = true;
      window.location.hash = next;
      queueMicrotask(() => {
        applyingHashRef.current = false;
      });
    }
  }, [patchRoute]);

  const setMerchantView = useCallback((view) => {
    const next = typeof view === 'function' ? view(routeRef.current.merchantView) : view;
    patchRoute({ merchantView: next });
  }, [patchRoute]);

  useEffect(() => {
    const applyFromLocation = () => {
      const parsed = parseHash(window.location.hash);
      applyingHashRef.current = true;
      routeRef.current = parsed;
      setActiveTabState(parsed.activeTab);
      setDashPageState(parsed.dashPage);
      setMerchantViewState(parsed.merchantView);
      queueMicrotask(() => {
        applyingHashRef.current = false;
      });
    };
    window.addEventListener('hashchange', applyFromLocation);
    window.addEventListener('popstate', applyFromLocation);
    return () => {
      window.removeEventListener('hashchange', applyFromLocation);
      window.removeEventListener('popstate', applyFromLocation);
    };
  }, []);

  const [auditLogs, setAuditLogs] = useState([]);
  const [profileMenuOpen, setProfileMenuOpen] = useState(false);
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [notifications, setNotifications] = useState([]);
  const [unreadNotifications, setUnreadNotifications] = useState(0);
  const [paymentFilter, setPaymentFilter] = useState(EMPTY_DATE_FILTER);
  const [exceptionFilter, setExceptionFilter] = useState(EMPTY_DATE_FILTER);
  const [auditFilter, setAuditFilter] = useState(EMPTY_DATE_FILTER);
  const [inquiryDate, setInquiryDate] = useState('');
  const [auditSource, setAuditSource] = useState('all');
  const [auditActionType, setAuditActionType] = useState('all');
  const [payments, setPayments] = useState([]);
  const [paymentsMeta, setPaymentsMeta] = useState(null);
  const [paymentSearch, setPaymentSearch] = useState('');
  const [paymentPage, setPaymentPage] = useState(1);
  const [paymentStatus, setPaymentStatus] = useState('all');
  const [exceptionSearch, setExceptionSearch] = useState(null);
  const [withdrawAvailability, setWithdrawAvailability] = useState(null);
  const [withdrawHistory, setWithdrawHistory] = useState([]);
  const [lastWithdrawal, setLastWithdrawal] = useState(null);
  const [withdrawPreview, setWithdrawPreview] = useState(null);
  const [withdrawing, setWithdrawing] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [drawerData, setDrawerData] = useState({
    payment_id: '',
    mismatch_type: '',
    delta: null,
    explanation: '',
  });
  const [toasts, setToasts] = useState([]);

  const demoProducts = useMemo(() => ([
    { id: 'earbuds', name: 'Premium Wireless Earbuds', subtitle: 'Active noise cancellation with 24-hour battery life and crisp audio quality.', price: 4999, image: '/products/earbuds.jpg' },
    { id: 'lamp', name: 'Ergo LED Desk Lamp', subtitle: 'Adjustable color temperature and brightness with sleek aluminum finish.', price: 2499, image: '/products/lamp.jpg' },
    { id: 'notebook', name: 'Professional Notebook Set', subtitle: 'Set of 3 premium dotted journals with 100gsm acid-free paper.', price: 899, image: '/products/notebook.jpg' },
    { id: 'keyboard', name: 'Mechanical Keyboard', subtitle: 'Tactile brown switches with customizable RGB backlighting and compact layout.', price: 6500, image: '/products/keyboard.jpg' },
    { id: 'monitor', name: 'Ergonomic Monitor Stand', subtitle: 'Raises the display to eye level for better posture during long finance close days.', price: 3200, image: '/products/stand.jpg' },
    { id: 'hub', name: '7-in-1 USB-C Hub', subtitle: 'HDMI, SD card reader, and multiple USB ports for a clean merchant desk.', price: 1899, image: '/products/hub.jpg' },
  ]), []);

  const merchantSubtotal = cart.reduce((sum, item) => sum + item.price * item.qty, 0);
  const merchantDiscount = 0;
  const merchantTax = Math.round(merchantSubtotal * 0.18);
  const merchantTotal = merchantSubtotal + merchantTax - merchantDiscount;

  const triggerToast = useCallback((message, type = 'success') => {
    const id = Date.now() + Math.random();
    setToasts((prev) => [...prev, { id, message, type }]);
    window.setTimeout(() => {
      setToasts((prev) => prev.filter((toast) => toast.id !== id));
    }, 4500);
  }, []);

  const fetchExceptions = useCallback(async () => {
    try {
      const data = await api.exceptions(false);
      setExceptions(data);
      return data;
    } catch {
      setExceptions([]);
      return [];
    }
  }, []);

  const fetchExceptionSearch = useCallback(async () => {
    try {
      const query = `${dateQuery(exceptionFilter)}&q=${encodeURIComponent(searchQuery)}&mismatch_type=${encodeURIComponent(mismatchFilter)}&page=${exceptionPage}&page_size=${DASHBOARD_PAGE_SIZE}&include_closed=false`;
      const data = await api.searchExceptions(query);
      setExceptionSearch(data);
      return data;
    } catch {
      setExceptionSearch(null);
      return null;
    }
  }, [exceptionFilter, exceptionPage, mismatchFilter, searchQuery]);

  const fetchPayments = useCallback(async () => {
    try {
      const query = `${dateQuery(paymentFilter)}&q=${encodeURIComponent(paymentSearch)}&page=${paymentPage}&page_size=100&status=${encodeURIComponent(paymentStatus)}`;
      const data = await api.payments(query);
      setPayments(data.records || []);
      setPaymentsMeta(data);
      return data;
    } catch {
      setPayments([]);
      setPaymentsMeta(null);
      return null;
    }
  }, [paymentFilter, paymentPage, paymentSearch, paymentStatus]);

  const fetchNotifications = useCallback(async () => {
    try {
      const data = await api.notifications();
      setNotifications(data.notifications || []);
      setUnreadNotifications(data.unread || 0);
    } catch {
      /* keep last */
    }
  }, []);

  const fetchWithdrawals = useCallback(async (asOf, historyFilter = EMPTY_DATE_FILTER, q = '') => {
    try {
      const avail = await api.withdrawalAvailability(asOf);
      setWithdrawAvailability(avail);
      const params = new URLSearchParams();
      if (q) params.set('q', q);
      if (historyFilter?.preset && historyFilter.preset !== 'all') {
        const bound = dateQuery(historyFilter);
        new URLSearchParams(bound).forEach((value, key) => params.set(key, value));
      }
      const data = await api.withdrawals(params.toString());
      setWithdrawHistory(data.history || []);
      setLastWithdrawal(data.last || null);
    } catch {
      setWithdrawAvailability(null);
    }
  }, []);

  const fetchAuditTrail = useCallback(async () => {
    try {
      const params = new URLSearchParams(dateQuery(auditFilter));
      params.set('limit', '100');
      if (auditSource !== 'all') params.set('source', auditSource);
      if (auditActionType !== 'all') params.set('action_type', auditActionType);
      if (auditSearch) params.set('q', auditSearch);
      const data = await api.auditQuery(params.toString());
      setAuditLogs(Array.isArray(data) ? data : []);
    } catch {
      /* keep last known trail */
    }
  }, [auditActionType, auditFilter, auditSearch, auditSource]);

  const fetchAnalyticsSummary = useCallback(async () => {
    try {
      const data = await api.analytics();
      setAnalytics(data);
    } catch {
      setAnalytics(null);
    }
  }, []);

  const fetchFinanceViews = useCallback(async () => {
    try {
      const [nextCash, nextSources, nextTax] = await Promise.all([
        api.cash(),
        api.sources(),
        api.taxLines(),
      ]);
      setCash(nextCash);
      setSources(nextSources);
      setTaxLines(nextTax);
    } catch {
      /* views populate after a successful reconcile */
    }
  }, []);

  const refreshAfterRun = useCallback(async (nextMetrics) => {
    if (nextMetrics) setMetrics(nextMetrics);
    setReconciliationRun(true);
    setBatchLoaded(true);
    await Promise.all([
      fetchExceptions(),
      fetchExceptionSearch(),
      fetchAuditTrail(),
      fetchAnalyticsSummary(),
      fetchFinanceViews(),
      fetchNotifications(),
      fetchPayments(),
    ]);
  }, [fetchAnalyticsSummary, fetchAuditTrail, fetchExceptionSearch, fetchExceptions, fetchFinanceViews, fetchNotifications, fetchPayments]);

  const checkExistingSession = useCallback(async () => {
    try {
      const metricsData = await api.metrics();
      await refreshAfterRun(metricsData);
    } catch {
      try {
        const status = await api.batchStatus();
        setBatchLoaded(Boolean(status.loaded));
      } catch {
        setBatchLoaded(false);
      }
    } finally {
      setSessionReady(true);
    }
  }, [refreshAfterRun]);

  const checkBackendConnection = useCallback(async () => {
    try {
      await api.health();
      setIsConnected(true);
      await checkExistingSession();
    } catch {
      setIsConnected(false);
      window.setTimeout(checkBackendConnection, 6000);
    }
  }, [checkExistingSession]);

  useEffect(() => {
    checkBackendConnection();
  }, [checkBackendConnection]);

  useEffect(() => {
    if (chatBottomRef.current) {
      chatBottomRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [chatMessages, chatLoading]);

  useEffect(() => {
    setExceptionPage(1);
  }, [mismatchFilter, searchQuery, exceptionFilter]);

  useEffect(() => {
    if (reconciliationRun) fetchExceptionSearch();
  }, [reconciliationRun, fetchExceptionSearch]);

  useEffect(() => {
    if (reconciliationRun) fetchAuditTrail();
  }, [reconciliationRun, fetchAuditTrail]);

  const handleLoadBatch = useCallback(async () => {
    if (!isConnected) {
      triggerToast('Backend is offline. Start FastAPI on port 8000 first.', 'danger');
      return null;
    }
    try {
      const data = await api.loadBatch();
      setBatchLoaded(true);
      setReconciliationRun(false);
      setCloseReport(null);
      setMetrics({
        total_records: data.loaded,
        match_rate: 0,
        matched: 0,
        exceptions: 0,
        amount_reconciled: 0,
        batch: data.batch,
      });
      triggerToast(`Batch loaded: ${data.loaded} Razorpay-shaped records.`, 'success');
      await fetchAuditTrail();
      await fetchAnalyticsSummary();
      return data;
    } catch (error) {
      triggerToast(error.message || 'Failed to load transaction batch.', 'danger');
      return null;
    }
  }, [fetchAnalyticsSummary, fetchAuditTrail, isConnected, triggerToast]);

  const handleRunReconciliation = useCallback(async (options = {}) => {
    const { force = false } = options;
    if (!isConnected) {
      triggerToast('Backend is offline. Start the FastAPI backend first.', 'danger');
      return null;
    }
    if (!force && !batchLoaded) {
      triggerToast('Load a batch before running reconciliation.', 'warning');
      return null;
    }
    try {
      const metricsData = await api.runReconciliation();
      setCloseReport(null);
      await refreshAfterRun(metricsData);
      triggerToast('Reconciliation complete. Exceptions isolated with explanations.', 'success');
      return metricsData;
    } catch (error) {
      triggerToast(error.message || 'Reconciliation run failed.', 'danger');
      return null;
    }
  }, [batchLoaded, isConnected, refreshAfterRun, triggerToast]);

  const loadAndReconcileBatch = useCallback(async () => {
    if (!isConnected) return;
    if (!batchLoaded) {
      const loaded = await handleLoadBatch();
      if (!loaded) return;
    }
    if (!reconciliationRun) {
      await handleRunReconciliation({ force: true });
    }
  }, [batchLoaded, handleLoadBatch, handleRunReconciliation, isConnected, reconciliationRun]);

  useEffect(() => {
    if (!sessionReady || !isConnected || activeTab !== 'dashboard' || reconciliationRun) {
      return;
    }
    loadAndReconcileBatch();
  }, [activeTab, isConnected, loadAndReconcileBatch, reconciliationRun, sessionReady]);

  useEffect(() => {
    if (!sessionReady || !isConnected || activeTab !== 'dashboard' || !reconciliationRun) return undefined;

    const refreshLiveDashboard = async () => {
      try {
        const nextMetrics = await api.metrics();
        setMetrics(nextMetrics);
        await fetchExceptions();
        await fetchExceptionSearch();
        await fetchNotifications();
      } catch {
        /* stay on last snapshot */
      }
    };

    const intervalId = window.setInterval(refreshLiveDashboard, 20000);
    return () => window.clearInterval(intervalId);
  }, [activeTab, fetchExceptionSearch, fetchExceptions, fetchNotifications, isConnected, reconciliationRun, sessionReady]);

  const handleGenerateFresh = useCallback(async () => {
    if (!isConnected) {
      triggerToast('Backend is offline.', 'danger');
      return;
    }
    try {
      const data = await api.generateBatch(generateCount);
      setBatchLoaded(true);
      setCloseReport(null);
      triggerToast(`Fresh batch generated: ${data.loaded} records with a hidden answer key.`, 'success');
      await handleRunReconciliation({ force: true });
    } catch (error) {
      triggerToast(error.message || 'Could not generate a fresh batch.', 'danger');
    }
  }, [generateCount, handleRunReconciliation, isConnected, triggerToast]);

  const uploadBatchFile = useCallback(async (file) => {
    if (!file) return null;
    const allowed = ['csv', 'xlsx', 'xls', 'txt'];
    const extension = file.name.split('.').pop()?.toLowerCase();
    if (extension && !allowed.includes(extension)) {
      triggerToast('Unsupported file type. Use CSV, XLSX, XLS, or TXT.', 'danger');
      return null;
    }
    if (!isConnected) {
      triggerToast('Backend is offline. Start the FastAPI backend first.', 'danger');
      return null;
    }
    try {
      const data = await api.uploadBatch(file);
      setBatchLoaded(true);
      setReconciliationRun(false);
      setCloseReport(null);
      setIngestReport(data.validation || null);
      const malformed = data.validation?.malformed_count || 0;
      triggerToast(
        malformed
          ? `${file.name} uploaded (${data.loaded} rows, ${malformed} malformed). Review the ingest report, then reconcile.`
          : `${file.name} uploaded (${data.loaded} rows). Running reconciliation.`,
        malformed ? 'warning' : 'success',
      );
      if (!malformed) {
        await handleRunReconciliation({ force: true });
      }
      return data;
    } catch (error) {
      triggerToast(error.message || 'Batch upload failed.', 'danger');
      return null;
    }
  }, [handleRunReconciliation, isConnected, triggerToast]);

  const handleBatchFileSelection = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    await uploadBatchFile(file);
    event.target.value = '';
  };

  const handleDropBatch = async (event) => {
    event.preventDefault();
    const file = event.dataTransfer?.files?.[0];
    if (file) await uploadBatchFile(file);
  };

  const downloadBatchTemplate = () => {
    downloadBlob(BATCH_TEMPLATE_CSV, 'razorpay_batch_template.csv', 'text/csv;charset=utf-8;');
  };

  const downloadCsvReport = () => {
    const rows = [
      ['Metric', 'Value'],
      ['Batch ID', metrics?.batch?.batch_id || '—'],
      ['Reconciliation Run', reconciliationRun ? 'Complete' : 'Pending'],
      ['Total Records', metrics?.total_records ?? 0],
      ['Match Rate', matchPercent(metrics)],
      ['Exceptions remaining', metrics?.unresolved_exceptions ?? metrics?.exceptions ?? 0],
      ['Amount Reconciled (INR)', metrics ? (metrics.amount_reconciled / 100).toFixed(2) : '0.00'],
      ['', ''],
    ];
    if (exceptions.length) {
      rows.push(['Payment ID', 'Mismatch Type', 'Priority', 'Delta', 'Explanation']);
      exceptions.forEach((exc) => {
        rows.push([
          exc.payment_id,
          exc.mismatch_type,
          exc.priority || '',
          exc.delta !== null && exc.delta !== undefined ? (exc.delta / 100).toFixed(2) : '',
          exc.explanation,
        ]);
      });
    }
    const csvData = rows.map((row) => row.map((cell) => `"${String(cell).replace(/"/g, '""')}"`).join(',')).join('\n');
    downloadBlob(csvData, 'razorpay_reconciliation_report.csv', 'text/csv;charset=utf-8;');
    triggerToast('CSV export downloaded.', 'success');
  };

  const downloadWordReport = async () => {
    if (!reconciliationRun) {
      triggerToast('Reconcile a batch before downloading the close report.', 'warning');
      return;
    }
    try {
      const blob = await api.wordReport();
      downloadBlob(blob, 'razorai-close-report.docx', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document');
      triggerToast('Word close report downloaded.', 'success');
    } catch (error) {
      triggerToast(error.message || 'Word report unavailable right now.', 'warning');
    }
  };

  const downloadAnalysisReport = async () => {
    try {
      const data = await api.chat('Prepare a short executive reconciliation summary with risks, total records, exception count, cash position, and suggested next steps.');
      const reportText = [
        'Razor-AI Finance Controller — close report',
        `Match rate: ${matchPercent(metrics)}`,
        `Total records: ${metrics?.total_records ?? 0}`,
        `Open exceptions: ${metrics?.unresolved_exceptions ?? metrics?.exceptions ?? 0}`,
        `Available cash: ${cash ? cash.available_rupees : 'n/a'}`,
        '',
        'Gemini summary:',
        data.answer,
      ].join('\n');
      downloadBlob(reportText, 'razorpay_analysis_report.txt', 'text/plain;charset=utf-8;');
      triggerToast('Analysis report exported.', 'success');
    } catch {
      triggerToast('Gemini report export unavailable right now.', 'warning');
    }
  };

  const appendChatMessage = (message) => {
    setChatMessages((prev) => [...prev, message].slice(-CHAT_MESSAGE_LIMIT));
  };

  const sendChat = async (queryText) => {
    if (!isConnected || !queryText.trim()) return;
    appendChatMessage({ id: Date.now(), sender: 'user', text: queryText });
    setChatLoading(true);
    try {
      const filter = paymentFilter?.preset && paymentFilter.preset !== 'all'
        ? paymentFilter
        : (exceptionFilter?.preset && exceptionFilter.preset !== 'all' ? exceptionFilter : EMPTY_DATE_FILTER);
      const data = await api.chat(queryText, {
        date: inquiryDate || (filter.preset === 'custom' ? filter.start : '') || undefined,
        preset: filter.preset !== 'all' ? filter.preset : undefined,
        start: filter.start || undefined,
        end: filter.end || undefined,
        batch_id: metrics?.batch?.batch_id || undefined,
        language: getLocale(),
      });
      if (data.scope?.date) {
        setInquiryDate(data.scope.date);
      }
      appendChatMessage({
        id: Date.now() + 1,
        sender: 'bot',
        text: data.answer,
        groundedIn: data.grounded_in,
        pendingConfirmation: data.pending_confirmation || null,
        aiAvailable: data.ai_available,
        scope: data.scope || null,
        toolUsed: data.tool_used || null,
        toolPayload: data.tool_payload ?? null,
      });
      if (data.executed) {
        await refreshAfterRun(data.executed.batch_metrics);
      }
      fetchAuditTrail();
    } catch {
      appendChatMessage({
        id: Date.now() + 1,
        sender: 'bot',
        text: 'Chat is unavailable. The rule engine still holds the exception list, cash position, and GST lines.',
      });
    } finally {
      setChatLoading(false);
    }
  };

  const handleSendChat = async (event) => {
    if (event) event.preventDefault();
    const queryText = chatInput.trim();
    setChatInput('');
    await sendChat(queryText);
  };

  const handleSuggestedClick = (query) => sendChat(query);

  const handleConfirmChatAction = async (confirm) => {
    try {
      const data = await api.confirmChatAction(confirm);
      appendChatMessage({
        id: Date.now() + 1,
        sender: 'bot',
        text: confirm ? `Confirmed. ${data.pending?.action} applied to ${data.pending?.payment_id}.` : 'Cancelled. No books were changed.',
      });
      if (confirm && data.result?.batch_metrics) {
        await refreshAfterRun(data.result.batch_metrics);
      }
      fetchAuditTrail();
    } catch (error) {
      triggerToast(error.message || 'Could not confirm that action.', 'danger');
    }
  };

  const handleResetDemo = async () => {
    if (!isConnected) return;
    try {
      await api.reset();
      setBatchLoaded(false);
      setReconciliationRun(false);
      setMetrics(null);
      setAnalytics(null);
      setExceptions([]);
      setCash(null);
      setSources(null);
      setTaxLines(null);
      setCloseReport(null);
      setSearchQuery('');
      setAuditSearch('');
      setMismatchFilter('all');
      setPaymentStatus('all');
      setPaymentSearch('');
      setPaymentPage(1);
      setChatMessages([initialChatMessage()]);
      triggerToast('Session reset. Load a new batch to close the books again.', 'warning');
      fetchAuditTrail();
    } catch {
      triggerToast('Error resetting demo state.', 'danger');
    }
  };

  const handleCloseBooks = async () => {
    if (!isConnected) {
      triggerToast('Backend is offline.', 'danger');
      return;
    }
    setClosingBooks(true);
    try {
      if (!batchLoaded) {
        const loaded = await handleLoadBatch();
        if (!loaded) return;
      }
      if (!reconciliationRun) {
        await handleRunReconciliation({ force: true });
      }
      const report = await api.closeBooks();
      setCloseReport(report);
      await refreshAfterRun(report.final);
      setCash(report.cash);
      setSources(report.sources);
      setTaxLines(report.tax);
      triggerToast(
        `Books closed. Auto-resolved ${report.auto_resolved}. ${report.remaining_exceptions.length} honest exceptions remain.`,
        report.remaining_exceptions.length ? 'warning' : 'success',
      );
      setDashPage('cash');
    } catch (error) {
      triggerToast(error.message || 'Could not close the books.', 'danger');
    } finally {
      setClosingBooks(false);
    }
  };

  const handleResolveException = async (paymentId, action, note = '', remember = false) => {
    setResolvingId(paymentId);
    try {
      const result = await api.resolveException(paymentId, action, note, remember);
      await refreshAfterRun(result.batch_metrics);
      if (action === 'escalate' || action === 'reject') {
        triggerToast(`${paymentId} stays on the honest exception list.`, 'warning');
      } else if (['acknowledge', 'investigate', 'assign', 'add_note', 'reopen'].includes(action)) {
        triggerToast(`${paymentId}: ${action.replace('_', ' ')} recorded in the audit trail.`, 'success');
      } else {
        triggerToast(`${paymentId} ${action === 'waive' ? 'waived' : 'corrected'} and re-run through the engine.`, 'success');
      }
    } catch (error) {
      triggerToast(error.message || 'Could not resolve this exception.', 'danger');
    } finally {
      setResolvingId(null);
    }
  };

  const handleInvestigate = async (paymentId) => {
    try {
      const data = await api.investigate(paymentId);
      setInvestigation(data);
      setDifference(data.waterfall || null);
      triggerToast(`Investigation complete for ${paymentId}.`, 'success');
      return data;
    } catch (error) {
      triggerToast(error.message || 'Investigation failed.', 'danger');
      return null;
    }
  };

  const handleExplainDifference = async (paymentId) => {
    try {
      const data = await api.difference(paymentId);
      setDifference(data);
      return data;
    } catch (error) {
      triggerToast(error.message || 'Could not explain this difference.', 'danger');
      return null;
    }
  };

  const handleWhatIf = async (payload) => {
    try {
      const data = await api.whatIf(payload);
      setWhatIfResult(data);
      return data;
    } catch (error) {
      triggerToast(error.message || 'What-if calculation failed.', 'danger');
      return null;
    }
  };

  const addToCart = useCallback((product) => {
    if (!product?.id) return;
    setCart((prev) => {
      const found = prev.find((item) => item.id === product.id);
      if (found) {
        return prev.map((item) => (item.id === product.id ? { ...item, qty: item.qty + 1 } : item));
      }
      return [...prev, { ...product, qty: 1 }];
    });
    triggerToast(`${product.name} added to cart.`, 'success');
  }, [triggerToast]);

  const updateCartQty = useCallback((productId, delta) => {
    if (!productId || !delta) return;
    setCart((prev) => prev
      .map((item) => (item.id === productId ? { ...item, qty: Math.max(0, item.qty + delta) } : item))
      .filter((item) => item.qty > 0));
  }, []);

  const removeCartItem = useCallback((productId) => {
    if (!productId) return;
    setCart((prev) => prev.filter((item) => item.id !== productId));
  }, []);

  const handleMerchantCheckout = async ({ synthetic = false } = {}) => {
    if (!cart.length) {
      triggerToast('Add a product to the cart before checkout.', 'warning');
      return;
    }
    const amount = Number(merchantTotal.toFixed(2));
    const extra = {
      items: cart.map((item) => ({ id: item.id, name: item.name, qty: item.qty, price: item.price })),
      customer_name: checkoutForm.name || 'Northwind Demo',
      customer_email: checkoutForm.email || 'demo@northwind.test',
      payment_method: 'razorpay',
    };
    const outcome = checkoutForm.aiOutcome || 'clean';

    const applySuccess = async (data) => {
      setLastPayment({
        ...data.this_payment,
        amountPaid: amount,
        method: data.this_payment?.payment_method || 'razorpay',
      });
      setPaymentFilter(EMPTY_DATE_FILTER);
      setPaymentStatus('all');
      setPaymentSearch('');
      setPaymentPage(1);
      await refreshAfterRun(data.batch_metrics);
      setMerchantView('success');
      setCart([]);
      if (data.this_payment?.reconciliation_status === 'exception') {
        triggerToast(`Payment ${data.this_payment.payment_id} flagged. Open notifications to investigate.`, 'warning');
        setDashPage('exceptions');
        setSelectedExcId(data.this_payment.payment_id);
      } else {
        triggerToast('Payment captured. It is now in the reconciliation batch.', 'success');
      }
    };

    const runSynthetic = async () => {
      const data = await api.simulatePayment(amount, outcome, extra);
      await applySuccess(data);
    };

    setCheckoutBusy(true);
    try {
      if (synthetic) {
        await runSynthetic();
        return;
      }
      let order;
      try {
        order = await api.createRazorpayOrder({ amount_rupees: amount, outcome, ...extra });
      } catch (error) {
        if (String(error.message || '').includes('not configured')) {
          triggerToast('Razorpay test keys are not set — using synthetic capture.', 'warning');
          await runSynthetic();
          return;
        }
        throw error;
      }
      await loadRazorpayScript();
      const response = await openRazorpayCheckout({
        key: order.key_id,
        amount: order.amount,
        currency: order.currency || 'INR',
        name: 'Northwind Goods',
        description: 'Demo checkout',
        order_id: order.order_id,
        prefill: {
          name: extra.customer_name,
          email: extra.customer_email,
          contact: checkoutForm.phone?.trim() || '9999999999',
        },
        notes: { demo: 'northwind' },
        theme: { color: '#0C2651' },
      });
      const data = await api.verifyRazorpayPayment({
        razorpay_order_id: response.razorpay_order_id,
        razorpay_payment_id: response.razorpay_payment_id,
        razorpay_signature: response.razorpay_signature,
      });
      await applySuccess(data);
    } catch (error) {
      if (String(error.message || '') === 'Checkout cancelled') {
        triggerToast('Checkout cancelled.', 'warning');
      } else {
        triggerToast(error.message || 'Checkout failed. Please try again.', 'danger');
      }
    } finally {
      setCheckoutBusy(false);
    }
  };

  const closeDrawer = () => setDrawerOpen(false);

  const handleRefundOrder = async (paymentId, amountRupees, confirm = false) => {
    try {
      const data = await api.refundOrder(paymentId, amountRupees, confirm);
      if (data.requires_confirmation) return data;
      await refreshAfterRun(data.batch_metrics);
      if (data.cash) setCash(data.cash);
      await fetchNotifications();
      const flagged = (data.notifications || []).some((item) => item.mismatch_type && !String(item.mismatch_type).startsWith('refund_initiated'));
      triggerToast(
        flagged
          ? `Refund posted on ${paymentId}. Payment flagged — open notifications.`
          : `Refund posted on ${paymentId}. Cash and GST have been recalculated.`,
        flagged ? 'warning' : 'success',
      );
      return data;
    } catch (error) {
      triggerToast(error.message || 'Refund failed.', 'danger');
      return null;
    }
  };
  const handleOpenNotification = async (item) => {
    setNotificationsOpen(false);
    setActiveTab('dashboard');
    const page = flagDestination(item);
    setDashPage(page);
    setSelectedExcId(item.payment_id);
    try {
      await api.markNotificationRead(item.id);
      await fetchNotifications();
    } catch {
      /* still navigate */
    }
  };

  const handleMarkAllNotificationsRead = async () => {
    try {
      await api.markAllNotificationsRead();
      await fetchNotifications();
    } catch (error) {
      triggerToast(error.message || 'Could not mark notifications read.', 'danger');
    }
  };

  const handlePreviewWithdraw = useCallback(async (amountRupees, asOf) => {
    try {
      const data = await api.withdrawalPreview(amountRupees, asOf);
      setWithdrawPreview(data);
      return data;
    } catch (error) {
      setWithdrawPreview({ can_withdraw: false, errors: [error.message], steps: [] });
      return null;
    }
  }, []);

  const handleConfirmWithdraw = async (amountRupees, asOf) => {
    setWithdrawing(true);
    try {
      const result = await api.createWithdrawal(amountRupees, asOf);
      triggerToast(result.message || 'Synthetic withdrawal recorded.', 'success');
      await Promise.all([fetchFinanceViews(), fetchAuditTrail(), fetchWithdrawals(asOf), fetchNotifications()]);
      setWithdrawAvailability(result.availability);
      setLastWithdrawal(result.withdrawal);
      return true;
    } catch (error) {
      triggerToast(error.message || 'Withdrawal rejected.', 'danger');
      return false;
    } finally {
      setWithdrawing(false);
    }
  };

  const handleOpenDrawer = (exc) => {
    setDrawerData({
      payment_id: exc.payment_id,
      mismatch_type: exc.mismatch_type || '',
      delta: exc.delta,
      explanation: exc.explanation,
    });
    setDrawerOpen(true);
  };

  const handleGroundedTagClick = (paymentId) => {
    const found = exceptions.find((item) => item.payment_id === paymentId);
    handleOpenDrawer(found || {
      payment_id: paymentId,
      mismatch_type: 'matched',
      delta: 0,
      explanation: 'This payment resolved clean and matched settlement records.',
    });
  };

  const filteredExceptions = exceptions.filter((exc) => {
    const query = searchQuery.trim().toLowerCase();
    const haystack = [exc.payment_id, exc.mismatch_type, exc.explanation, exc.priority]
      .filter(Boolean)
      .join(' ')
      .toLowerCase();
    const matchesSearch = !query || haystack.includes(query);
    const matchesType = mismatchFilter === 'all' || exc.mismatch_type === mismatchFilter;
    return matchesSearch && matchesType;
  });

  const pagedExceptions = exceptionSearch?.records || filteredExceptions.slice(
    (exceptionPage - 1) * DASHBOARD_PAGE_SIZE,
    exceptionPage * DASHBOARD_PAGE_SIZE,
  );

  const visibleAuditLogs = auditLogs.slice(
    (auditPage - 1) * DASHBOARD_PAGE_SIZE,
    auditPage * DASHBOARD_PAGE_SIZE,
  );

  const totalExceptionPages = exceptionSearch?.total_pages || Math.max(1, Math.ceil(filteredExceptions.length / DASHBOARD_PAGE_SIZE));
  const totalAuditPages = Math.max(1, Math.ceil(auditLogs.length / DASHBOARD_PAGE_SIZE));
  const visibleChatMessages = chatMessages.slice(-CHAT_MESSAGE_LIMIT);
  const selectedException = exceptions.find((item) => item.payment_id === selectedExcId)
    || pagedExceptions.find((item) => item.payment_id === selectedExcId)
    || null;

  const value = {
    activeTab, setActiveTab,
    dashPage, setDashPage, goToAdmin,
    expandedExc, setExpandedExc,
    selectedExcId, setSelectedExcId,
    selectedException,
    sidebarOpen, setSidebarOpen,
    isConnected,
    batchLoaded,
    reconciliationRun,
    closingBooks,
    resolvingId,
    metrics, analytics, exceptions, cash, sources, taxLines, closeReport,
    investigation, difference, whatIfResult, ingestReport,
    searchQuery, setSearchQuery,
    auditSearch, setAuditSearch,
    mismatchFilter, setMismatchFilter,
    exceptionPage, setExceptionPage,
    auditPage, setAuditPage,
    generateCount, setGenerateCount,
    chatInput, setChatInput,
    chatLoading, chatBottomRef, visibleChatMessages,
    batchInputRef,
    merchantView, setMerchantView,
    cart, demoProducts, checkoutForm, setCheckoutForm, checkoutBusy,
    merchantSubtotal, merchantDiscount, merchantTax, merchantTotal, lastPayment,
    auditLogs, visibleAuditLogs, filteredAuditLogs: auditLogs,
    profileMenuOpen, setProfileMenuOpen,
    notificationsOpen, setNotificationsOpen, notifications, unreadNotifications,
    handleOpenNotification, handleMarkAllNotificationsRead,
    paymentFilter, setPaymentFilter, payments, paymentsMeta, fetchPayments,
    inquiryDate, setInquiryDate,
    paymentSearch, setPaymentSearch, paymentPage, setPaymentPage,
    paymentStatus, setPaymentStatus,
    exceptionFilter, setExceptionFilter, exceptionSearch, fetchExceptionSearch,
    auditFilter, setAuditFilter, auditSource, setAuditSource, auditActionType, setAuditActionType,
    withdrawAvailability, withdrawHistory, lastWithdrawal, withdrawPreview, withdrawing,
    fetchWithdrawals, handlePreviewWithdraw, handleConfirmWithdraw,
    drawerOpen, drawerData, closeDrawer, handleOpenDrawer, handleGroundedTagClick,
    toasts,
    filteredExceptions, pagedExceptions, totalExceptionPages, totalAuditPages,
    triggerToast,
    handleLoadBatch,
    handleRunReconciliation,
    handleGenerateFresh,
    handleBatchFileSelection,
    handleDropBatch,
    downloadBatchTemplate,
    downloadCsvReport,
    downloadWordReport,
    downloadAnalysisReport,
    handleSendChat,
    handleSuggestedClick,
    handleConfirmChatAction,
    handleResetDemo,
    handleCloseBooks,
    handleResolveException,
    handleInvestigate,
    handleExplainDifference,
    handleWhatIf,
    addToCart, updateCartQty, removeCartItem, handleMerchantCheckout, handleRefundOrder,
    DASHBOARD_PAGE_SIZE,
  };

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}
