const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

async function parseError(response) {
  try {
    const payload = await response.json();
    return payload.detail || payload.message || `Request failed (${response.status})`;
  } catch {
    return `Request failed (${response.status})`;
  }
}

async function request(path, options = {}) {
  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, options);
  } catch {
    throw new Error(
      'API host did not respond. Render free instances sleep — wait ~30s and retry. If this keeps happening, open the Render service and confirm it is Live.'
    );
  }
  if (!response.ok) {
    throw new Error(await parseError(response));
  }
  return response.json();
}

export const api = {
  baseUrl: API_BASE_URL,
  health: () => request('/'),
  loadBatch: () => request('/batch/load', { method: 'POST' }),
  generateBatch: (count = 100) => request(`/batch/generate-fresh?count=${count}`, { method: 'POST' }),
  uploadBatch: (file) => {
    const body = new FormData();
    body.append('file', file);
    return request('/batch/upload', { method: 'POST', body });
  },
  batchStatus: () => request('/batch/status'),
  runReconciliation: () => request('/reconcile/run', { method: 'POST' }),
  metrics: () => request('/reconcile/metrics'),
  exceptions: (includeClosed = false) => request(`/reconcile/exceptions?include_closed=${includeClosed}`),
  chat: async (question, context = {}) => {
    const payload = {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        question,
        date: context.date || undefined,
        preset: context.preset || undefined,
        start: context.start || undefined,
        end: context.end || undefined,
        batch_id: context.batch_id || undefined,
        language: context.language || undefined,
      }),
    };
    try {
      return await request('/chat', payload);
    } catch (error) {
      await new Promise((resolve) => window.setTimeout(resolve, 800));
      try {
        return await request('/chat', payload);
      } catch {
        throw error;
      }
    }
  },
  audit: (limit = 100) => request(`/audit-trail?limit=${limit}`),
  analytics: () => request('/analytics/summary'),
  cash: () => request('/cash/position'),
  sources: () => request('/ledgers/sources'),
  taxLines: () => request('/tax/lines'),
  closeBooks: () => request('/books/close', { method: 'POST' }),
  reset: () => request('/demo/reset', { method: 'POST' }),
  simulatePayment: (amountRupees, outcome, extra = {}) => request('/demo/simulate-payment', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ amount_rupees: amountRupees, outcome, ...extra }),
  }),
  createRazorpayOrder: (payload) => request('/demo/razorpay/create-order', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  }),
  verifyRazorpayPayment: (payload) => request('/demo/razorpay/verify', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  }),
  storeOrders: () => request('/demo/orders'),
  refundOrder: (paymentId, amountRupees, confirm = false) => request('/demo/refund', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ payment_id: paymentId, amount_rupees: amountRupees, confirm }),
  }),
  controllerOverview: (versus = 'yesterday') => request(`/controller/overview?versus=${encodeURIComponent(versus)}`),
  briefing: () => request('/controller/briefing'),
  whatChanged: (versus = 'yesterday') => request(`/controller/what-changed?versus=${encodeURIComponent(versus)}`),
  clusters: () => request('/controller/clusters'),
  actionQueue: () => request('/controller/action-queue'),
  opsHealth: () => request('/controller/health'),
  anomalies: () => request('/controller/anomalies'),
  refundIntel: () => request('/controller/refunds'),
  aging: () => request('/controller/aging'),
  performance: () => request('/controller/performance'),
  merchants: () => request('/controller/merchants'),
  cashWhy: () => request('/cash/why'),
  financeSearch: (q) => request(`/search?q=${encodeURIComponent(q || '')}`),
  timeline: (paymentId) => request(`/records/${encodeURIComponent(paymentId)}/timeline`),
  batchResolve: (payload) => request('/exceptions/batch-resolve', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  }),
  rules: () => request('/controller/rules'),
  createRule: (payload) => request('/controller/rules', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  }),
  updateRule: (id, payload) => request(`/controller/rules/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  }),
  deleteRule: (id) => request(`/controller/rules/${id}`, { method: 'DELETE' }),
  confirmChatAction: (confirm) => request('/chat/confirm', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ confirm }),
  }),
  resolveException: (paymentId, action, note = '', remember = false) => request('/exceptions/resolve', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ payment_id: paymentId, action, note, remember }),
  }),
  config: () => request('/config'),
  ingestReport: () => request('/batch/ingest-report'),
  investigate: (paymentId) => request(`/exceptions/${encodeURIComponent(paymentId)}/investigate`),
  difference: (paymentId) => request(`/exceptions/${encodeURIComponent(paymentId)}/difference`),
  notes: (paymentId) => request(`/exceptions/${encodeURIComponent(paymentId)}/notes`),
  recurring: () => request('/recurring'),
  whatIf: (payload) => request('/cash/what-if', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  }),
  payments: (query = '') => request(`/payments${query ? `?${query}` : ''}`),
  searchExceptions: (query = '') => request(`/exceptions/search${query ? `?${query}` : ''}`),
  notifications: () => request('/notifications'),
  markNotificationRead: (id) => request(`/notifications/${id}/read`, { method: 'POST' }),
  markAllNotificationsRead: () => request('/notifications/read-all', { method: 'POST' }),
  withdrawals: (query = '') => request(`/withdrawals${query ? `?${query}` : ''}`),
  withdrawalAvailability: (asOf) => request(`/withdrawals/availability${asOf ? `?as_of=${encodeURIComponent(asOf)}` : ''}`),
  withdrawalPreview: (amountRupees, asOf) => request('/withdrawals/preview', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ amount_rupees: amountRupees, as_of: asOf || null }),
  }),
  createWithdrawal: (amountRupees, asOf) => request('/withdrawals', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ amount_rupees: amountRupees, as_of: asOf || null }),
  }),
  auditQuery: (query = '') => request(`/audit-trail?${query}`),
  wordReport: async () => {
    const response = await fetch(`${API_BASE_URL}/reports/word`);
    if (!response.ok) {
      throw new Error(await parseError(response));
    }
    return response.blob();
  },
  daySummary: (date, paymentId) => {
    const params = new URLSearchParams();
    if (date) params.set('date', date);
    if (paymentId) params.set('payment_id', paymentId);
    const query = params.toString();
    return request(`/analytics/day${query ? `?${query}` : ''}`);
  },
  excelReport: async (date) => {
    const query = date ? `?date=${encodeURIComponent(date)}` : '';
    const response = await fetch(`${API_BASE_URL}/reports/excel${query}`);
    if (!response.ok) {
      throw new Error(await parseError(response));
    }
    return response.blob();
  },
};
