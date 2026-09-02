import React, { useEffect, useRef } from 'react';
import { Bell } from 'lucide-react';
import { useApp } from '../AppContext';
import { flagDestination, formatPaise, titleCaseType } from '../lib/format';

export default function NotificationMenu() {
  const {
    notifications, unreadNotifications, notificationsOpen, setNotificationsOpen,
    handleOpenNotification, handleMarkAllNotificationsRead, isConnected,
  } = useApp();
  const wrapRef = useRef(null);

  useEffect(() => {
    const onDoc = (event) => {
      if (wrapRef.current && !wrapRef.current.contains(event.target)) {
        setNotificationsOpen(false);
      }
    };
    document.addEventListener('mousedown', onDoc);
    return () => document.removeEventListener('mousedown', onDoc);
  }, [setNotificationsOpen]);

  return (
    <div className="db-topbar-menu-wrap" ref={wrapRef}>
      <button
        className="db-topbar-icon"
        title="Notifications"
        aria-label="Notifications"
        type="button"
        onClick={() => setNotificationsOpen((open) => !open)}
        disabled={!isConnected}
      >
        <Bell className="circ-nav-glyph" />
        {unreadNotifications > 0 ? <span className="db-bell-count">{unreadNotifications}</span> : null}
      </button>
      {notificationsOpen && (
        <div className="db-notify-menu" data-tour="notifications">
          <div className="db-notify-head">
            <strong>Notifications</strong>
            <button type="button" className="db-text-link" onClick={handleMarkAllNotificationsRead} disabled={!unreadNotifications}>
              Mark all read
            </button>
          </div>
          {notifications.length ? notifications.slice(0, 12).map((item) => (
            <button
              key={item.id}
              type="button"
              className={`db-notify-item ${item.read ? '' : 'unread'}`}
              onClick={() => handleOpenNotification(item)}
            >
              <span>{String(item.mismatch_type || '').startsWith('refund_initiated') ? `Refund · ${item.payment_id}` : `Flagged · ${item.payment_id}`}</span>
              <strong>{formatPaise(item.amount_paise)}</strong>
              <small>{titleCaseType(item.mismatch_type)} · {item.priority} · {flagDestination(item) === 'gst' ? 'GST' : flagDestination(item) === 'payments' ? 'Payments' : flagDestination(item) === 'withdraw' ? 'Withdraw' : 'Exceptions'}</small>
              <small className="text-dim">{item.reason}</small>
            </button>
          )) : (
            <p className="db-table-empty">No flagged-payment notifications yet.</p>
          )}
        </div>
      )}
    </div>
  );
}
