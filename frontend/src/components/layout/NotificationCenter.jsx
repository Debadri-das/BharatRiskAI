import { Bell, CheckCheck, ShieldAlert, X } from 'lucide-react';
import { useState } from 'react';
import { useNotificationStore } from '../../store/notificationStore';

const levelClass = { YELLOW: 'notice-yellow', ORANGE: 'notice-orange', RED: 'notice-red' };

export default function NotificationCenter() {
  const [open, setOpen] = useState(false);
  const notifications = useNotificationStore((state) => state.notifications);
  const markAllRead = useNotificationStore((state) => state.markAllRead);
  const clear = useNotificationStore((state) => state.clear);
  const unread = notifications.filter((item) => !item.read).length;

  return (
    <div className="notification-center">
      <button className="notification-trigger" onClick={() => setOpen((value) => !value)} aria-label="Open notifications">
        <Bell size={17} />
        {unread > 0 && <span className="notification-count">{unread > 9 ? '9+' : unread}</span>}
      </button>
      {open && (
        <section className="notification-panel panel">
          <div className="notification-heading">
            <div><span className="section-kicker"><ShieldAlert size={13} /> THREAT NOTIFICATIONS</span><h3>Early warnings</h3></div>
            <button className="notification-close" onClick={() => setOpen(false)} aria-label="Close notifications"><X size={16} /></button>
          </div>
          <div className="notification-actions">
            <button onClick={markAllRead}><CheckCheck size={14} /> Mark read</button>
            <button onClick={clear}>Clear</button>
          </div>
          {notifications.length === 0 ? <p className="notification-empty">No predicted threats have been received.</p> : (
            <div className="notification-list">
              {notifications.map((item) => (
                <article className={`notification-item ${levelClass[item.alertLevel] || ''} ${item.read ? 'read' : ''}`} key={item.id}>
                  <strong>{item.alertLevel} · {item.zoneName}</strong>
                  <span>{item.hazard} · {item.leadTimeMinutes || '—'} min lead time</span>
                  {item.advisory && <small>{item.advisory}</small>}
                  <time>{new Date(item.createdAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</time>
                </article>
              ))}
            </div>
          )}
        </section>
      )}
    </div>
  );
}
