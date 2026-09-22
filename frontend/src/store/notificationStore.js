import { create } from 'zustand';

const STORAGE_KEY = 'bharatrisk-notifications';
const MAX_NOTIFICATIONS = 40;
const severityRank = { GREEN: 0, YELLOW: 1, ORANGE: 2, RED: 3 };

function loadStored() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]');
  } catch {
    return [];
  }
}

function persist(notifications) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(notifications.slice(0, MAX_NOTIFICATIONS)));
}

export const useNotificationStore = create((set, get) => ({
  notifications: loadStored(),
  permission: typeof Notification === 'undefined' ? 'unsupported' : Notification.permission,
  addThreatNotifications: (alerts = []) => {
    const current = get().notifications;
    const now = Date.now();
    const additions = [];

    alerts
      .filter((alert) => severityRank[alert.alert_level] >= severityRank.YELLOW)
      .forEach((alert) => {
        const key = `${alert.zone_id}:${alert.primary_hazard}`;
        const previous = current.find((item) => item.key === key);
        const isEscalation = previous && severityRank[alert.alert_level] > severityRank[previous.alertLevel];
        const recentlyNotified = previous && now - previous.createdAt < 15 * 60 * 1000;
        if (recentlyNotified && !isEscalation) return;

        additions.push({
          id: `${key}:${alert.alert_level}:${now}`,
          key,
          alertLevel: alert.alert_level,
          zoneName: alert.zone_name,
          hazard: alert.primary_hazard,
          leadTimeMinutes: alert.lead_time_minutes,
          advisory: alert.advisory,
          createdAt: now,
          read: false,
        });
      });

    if (!additions.length) return;
    const next = [...additions, ...current].slice(0, MAX_NOTIFICATIONS);
    persist(next);
    set({ notifications: next });

    if (typeof Notification !== 'undefined' && Notification.permission === 'granted') {
      additions.forEach((item) => {
        new Notification(`${item.alertLevel} weather alert · ${item.zoneName}`, {
          body: `${item.hazard}. Expected in ${item.leadTimeMinutes || 'an unknown number of'} minutes.`,
          tag: item.key,
        });
      });
    }
  },
  requestPermission: async () => {
    if (typeof Notification === 'undefined') return 'unsupported';
    const permission = await Notification.requestPermission();
    set({ permission });
    return permission;
  },
  markAllRead: () => {
    const next = get().notifications.map((item) => ({ ...item, read: true }));
    persist(next);
    set({ notifications: next });
  },
  clear: () => {
    persist([]);
    set({ notifications: [] });
  },
}));
