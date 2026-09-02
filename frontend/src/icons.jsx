const iconStroke = {
  width: 18,
  height: 18,
  viewBox: '0 0 24 24',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 1.8,
  strokeLinecap: 'round',
  strokeLinejoin: 'round',
};

export const IconDashboard = (props) => (
  <svg {...iconStroke} {...props}>
    <rect x="3" y="3" width="7" height="7" rx="1.5" />
    <rect x="14" y="3" width="7" height="4.5" rx="1.5" />
    <rect x="14" y="12" width="7" height="9" rx="1.5" />
    <rect x="3" y="12" width="7" height="9" rx="1.5" />
  </svg>
);

export const IconReconciliation = (props) => (
  <svg {...iconStroke} {...props}>
    <path d="M7 7h10a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V9a2 2 0 0 1 2-2Z" />
    <path d="M8 7V5.5A1.5 1.5 0 0 1 9.5 4h5A1.5 1.5 0 0 1 16 5.5V7" />
    <path d="M8 12h8" />
    <path d="M12 8v8" />
  </svg>
);

export const IconExceptions = (props) => (
  <svg {...iconStroke} {...props}>
    <path d="M7 7h10l2 2v8a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V9a2 2 0 0 1 2-2Z" />
    <path d="M9 11h6" />
    <path d="M9 15h6" />
    <path d="M12 11v4" />
  </svg>
);

export const IconAudit = (props) => (
  <svg {...iconStroke} {...props}>
    <path d="M8 5.5A2.5 2.5 0 0 1 10.5 3h3A2.5 2.5 0 0 1 16 5.5v10.1A2.5 2.5 0 0 1 13.5 18h-3A2.5 2.5 0 0 1 8 15.5V5.5Z" />
    <path d="M10 8.5h4" />
    <path d="M10 12h4" />
    <path d="M10 15.5h3" />
  </svg>
);

export const IconReports = (props) => (
  <svg {...iconStroke} {...props}>
    <path d="M5 20V8.5A1.5 1.5 0 0 1 6.5 7H9l2 2h6.5A1.5 1.5 0 0 1 19 10.5V20" />
    <path d="M8 15h2" />
    <path d="M11 12h2" />
    <path d="M14 17h2" />
  </svg>
);

export const IconCash = (props) => (
  <svg {...iconStroke} {...props}>
    <rect x="3" y="6" width="18" height="12" rx="2" />
    <circle cx="12" cy="12" r="2.5" />
    <path d="M7 12h.01M17 12h.01" />
  </svg>
);

export const IconBell = (props) => (
  <svg {...iconStroke} {...props}>
    <path d="M15 17h5l-1.4-1.4A2 2 0 0 1 18 14.2V11a6 6 0 1 0-12 0v3.2a2 2 0 0 1-.6 1.4L4 17h5" />
    <path d="M10 20a2 2 0 0 0 4 0" />
  </svg>
);

export const IconCog = (props) => (
  <svg {...iconStroke} {...props}>
    <circle cx="12" cy="12" r="3.2" />
    <path d="M19.4 15a1.6 1.6 0 0 0 .3 1.7l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.6 1.6 0 0 0-1.7-.3 1.6 1.6 0 0 0-1 1.5V20a2 2 0 1 1-4 0v-.2A1.6 1.6 0 0 0 9.1 18a1.6 1.6 0 0 0-1.7.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1A1.6 1.6 0 0 0 4.6 15a1.6 1.6 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.2A1.6 1.6 0 0 0 4.6 9a1.6 1.6 0 0 0-.3-1.7L4.2 7.2a2 2 0 1 1 2.8-2.8l.1.1A1.6 1.6 0 0 0 9 4.6a1.6 1.6 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.2A1.6 1.6 0 0 0 15 4.6a1.6 1.6 0 0 0 1.7-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1A1.6 1.6 0 0 0 19.4 9c.4.2.8.5 1 1H21a2 2 0 1 1 0 4h-.2a1.6 1.6 0 0 0-1 1Z" />
  </svg>
);

export const IconUser = (props) => (
  <svg {...iconStroke} {...props}>
    <circle cx="12" cy="8" r="3.5" />
    <path d="M5 19c1.4-3 4-4.5 7-4.5s5.6 1.5 7 4.5" />
  </svg>
);

export const IconSparkles = (props) => (
  <svg {...iconStroke} {...props}>
    <path d="m12 2 1.5 4.5L18 8l-4.5 1.5L12 14l-1.5-4.5L6 8l4.5-1.5L12 2Z" />
    <path d="m19 14 1 3 3 1-3 1-1 3-1-3-3-1 3-1 1-3Z" />
  </svg>
);

export const IconSend = (props) => (
  <svg {...iconStroke} {...props}>
    <path d="M3 11.5 20 4l-4.5 16-3.7-6.5-8.8-2Z" />
    <path d="M20 4 11.8 12.2" />
  </svg>
);

export const IconUpload = (props) => (
  <svg {...iconStroke} {...props}>
    <path d="M12 16V4" />
    <path d="m7 9 5-5 5 5" />
    <path d="M4 18.5v.5a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-.5" />
  </svg>
);

export const IconChevronDown = (props) => (
  <svg {...iconStroke} {...props}>
    <path d="m6 9 6 6 6-6" />
  </svg>
);

export const IconBook = (props) => (
  <svg {...iconStroke} {...props}>
    <path d="M5 4.5A1.5 1.5 0 0 1 6.5 3H18v15H6.5A1.5 1.5 0 0 0 5 19.5V4.5Z" />
    <path d="M5 19.5A1.5 1.5 0 0 1 6.5 18H18" />
  </svg>
);

export const IconStore = (props) => (
  <svg {...iconStroke} {...props}>
    <path d="M4 10 6 4h12l2 6" />
    <path d="M4 10h16v8a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2v-8Z" />
    <path d="M10 22v-6h4v6" />
  </svg>
);

export const IconWithdraw = (props) => (
  <svg {...iconStroke} {...props}>
    <rect x="3" y="6" width="18" height="12" rx="2" />
    <path d="M12 9v6" />
    <path d="m9 12 3 3 3-3" />
  </svg>
);

export const IconChevronUp = (props) => (
  <svg {...iconStroke} {...props}>
    <path d="m6 15 6-6 6 6" />
  </svg>
);
