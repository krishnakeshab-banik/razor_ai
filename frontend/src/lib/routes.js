const DASH_PAGES = new Set([
  'home', 'payments', 'reconciliation', 'exceptions', 'cash', 'gst',
  'withdraw', 'audit', 'knowledge', 'guide', 'reports',
]);

const MERCHANT_VIEWS = new Set(['store', 'orders', 'cart', 'checkout', 'success']);

const DASH_ALIASES = {
  rules: 'knowledge',
  controller: 'home',
  dashboard: 'home',
};

const TAB_ALIASES = {
  market: 'merchant-checkout',
  marketplace: 'merchant-checkout',
  store: 'merchant-checkout',
  app: 'dashboard',
  controller: 'dashboard',
};

export function parseHash(hash) {
  const raw = String(hash || '').replace(/^#/, '').replace(/^\/+/, '');
  const parts = raw.split('/').filter(Boolean);
  if (!parts.length) {
    return { activeTab: 'overview', dashPage: 'home', merchantView: 'store' };
  }

  const head = parts[0].toLowerCase();
  if (head === 'how-it-works') {
    return { activeTab: 'how-it-works', dashPage: 'home', merchantView: 'store' };
  }
  if (head === 'roadmap') {
    return { activeTab: 'roadmap', dashPage: 'home', merchantView: 'store' };
  }

  const tab = TAB_ALIASES[head] || head;
  if (tab === 'merchant-checkout') {
    const viewRaw = (parts[1] || 'store').toLowerCase();
    const merchantView = MERCHANT_VIEWS.has(viewRaw) ? viewRaw : 'store';
    return { activeTab: 'merchant-checkout', dashPage: 'home', merchantView };
  }

  if (tab === 'dashboard') {
    const pageRaw = (parts[1] || 'home').toLowerCase();
    const mapped = DASH_ALIASES[pageRaw] || pageRaw;
    const dashPage = DASH_PAGES.has(mapped) ? mapped : 'home';
    return { activeTab: 'dashboard', dashPage, merchantView: 'store' };
  }

  return { activeTab: 'overview', dashPage: 'home', merchantView: 'store' };
}

export function toHash({ activeTab, dashPage, merchantView }) {
  if (activeTab === 'how-it-works') return '#/how-it-works';
  if (activeTab === 'roadmap') return '#/roadmap';
  if (activeTab === 'merchant-checkout') {
    if (merchantView && merchantView !== 'store') return `#/store/${merchantView}`;
    return '#/store';
  }
  if (activeTab === 'dashboard') {
    if (dashPage && dashPage !== 'home') {
      const slug = dashPage === 'knowledge' ? 'rules' : dashPage;
      return `#/dashboard/${slug}`;
    }
    return '#/dashboard';
  }
  return '#/';
}

export function sameHash(left, right) {
  const norm = (value) => {
    const raw = String(value || '#/');
    const withHash = raw.startsWith('#') ? raw : `#${raw}`;
    if (withHash === '#' || withHash === '#/') return '#/';
    return withHash.replace(/\/+$/, '');
  };
  return norm(left) === norm(right);
}
