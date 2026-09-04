export const DASHBOARD_PAGE_SIZE = 10;
export const CHAT_MESSAGE_LIMIT = 10;

export const BATCH_TEMPLATE_CSV = `payment_id,amount,order_id,settlement_id,fee,tax,refund_amount,status,created_at,settled_at,payment_method,source
pay_a54429fa9b,4528.17,order_1001,setl_1102,90.56,16.30,0,captured,2026-08-19,2026-08-21,upi,razorpay
pay_b11234cd44,1240.00,order_1002,setl_1103,24.80,4.46,0,captured,2026-08-20,2026-08-22,card,razorpay
pay_c88492ef18,845.60,order_1003,,16.91,3.04,0,captured,2026-08-21,,upi,razorpay
`;

export function formatDayLabel(stamp) {
  if (!stamp) return '';
  const raw = String(stamp).slice(0, 10);
  const parsed = new Date(`${raw}T00:00:00`);
  if (Number.isNaN(parsed.getTime())) return raw;
  return parsed.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
}

export function formatPaise(paise) {
  if (paise === null || paise === undefined || Number.isNaN(Number(paise))) {
    return '₹0.00';
  }
  return (Number(paise) / 100).toLocaleString('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 2,
  });
}

export function formatRupees(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return '₹0.00';
  }
  return Number(value).toLocaleString('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 2,
  });
}

export function formatCompactRupees(value) {
  const amount = Number(value || 0);
  const sign = amount < 0 ? '-' : '';
  const mag = Math.abs(amount);
  if (mag >= 100000) {
    return `${sign}₹${(mag / 100000).toFixed(1)}L`;
  }
  return formatRupees(amount);
}

export function formatDelta(paise) {
  if (paise === null || paise === undefined) return 'No delta';
  const direction = Number(paise) >= 0 ? 'Over by' : 'Short by';
  return `${direction} ${formatPaise(Math.abs(paise))}`;
}

export function titleCaseType(value) {
  if (!value) return 'Matched';
  return String(value).split('_').map((word) => word.charAt(0).toUpperCase() + word.slice(1)).join(' ');
}

const EVIDENCE_LABELS = {
  payment_id: 'Payment ID',
  settlement_id: 'Settlement ID',
  utr: 'Bank UTR',
  amount: 'Settlement amount',
  fee: 'Processing fee',
  tax: 'GST on fee',
  settlement_window: 'Settlement window',
};

export function evidenceLabel(signal) {
  return EVIDENCE_LABELS[signal] || titleCaseType(signal);
}

export function formatEvidenceDetail(detail) {
  if (detail === null || detail === undefined || detail === '') return 'Missing';
  return String(detail)
    .replace(/(\d+)\s*paise/gi, (_, n) => formatPaise(Number(n)))
    .replace(/\bfee (\d+) vs expected (\d+)/i, (_, a, b) => `fee ${formatPaise(a)} vs expected ${formatPaise(b)}`)
    .replace(/\bGST (\d+) vs expected (\d+)/i, (_, a, b) => `GST ${formatPaise(a)} vs expected ${formatPaise(b)}`);
}

export function friendlyExplanation(text) {
  return String(text || '').replace(
    /\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:[+-]\d{2}:\d{2})?/g,
    (stamp) => formatTimestamp(stamp),
  );
}

export function formatAge(createdAt) {
  if (!createdAt) return '—';
  const ms = Date.now() - new Date(createdAt).getTime();
  if (Number.isNaN(ms)) return '—';
  const days = Math.max(0, Math.floor(ms / 86400000));
  if (days < 1) {
    const hours = Math.max(0, Math.floor(ms / 3600000));
    return hours < 1 ? 'Today' : `${hours}h`;
  }
  return `${days}d`;
}

export function flagDestination(item) {
  const type = String(item?.mismatch_type || '');
  if (type.startsWith('refund')) return 'payments';
  if (type === 'tax_line_mismatch') return 'gst';
  if (type.includes('withdraw')) return 'withdraw';
  return 'exceptions';
}

export function formatTimestamp(value) {
  if (!value) return '—';
  const raw = String(value).trim();
  const hasZone = /[zZ]|[+-]\d{2}:?\d{2}$/.test(raw);
  const date = new Date(hasZone ? raw : raw.replace(' ', 'T'));
  if (Number.isNaN(date.getTime())) return raw;
  return date.toLocaleString('en-IN', {
    dateStyle: 'medium',
    timeStyle: 'short',
    ...(hasZone ? { timeZone: 'Asia/Kolkata' } : {}),
  });
}

export function matchPercent(metrics) {
  if (!metrics || metrics.match_rate === undefined || metrics.match_rate === null) return '--';
  return `${(metrics.match_rate * 100).toFixed(1)}%`;
}

export function downloadBlob(content, filename, type) {
  const blob = content instanceof Blob ? content : new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

export function initialChatMessage() {
  return {
    id: 1,
    sender: 'bot',
    text: 'I am Razor-AI. Matching is rule-based. Ask how to use a page, or about this batch’s exceptions, GST, and cash. I will not share keys, secrets, or customer contact fields.',
    isSuggested: true,
  };
}
