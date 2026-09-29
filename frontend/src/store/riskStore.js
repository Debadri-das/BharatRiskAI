import { create } from 'zustand';
import { api } from '../services/api';
import { demoDashboard } from '../services/demoData';

export const useRiskStore = create((set, get) => ({
  dashboard: demoDashboard(),
  nowcast: null,
  selectedZoneId: 1,
  load: async () => {
    try {
      const [dashboard, nowcast] = await Promise.all([
        api('/dashboard'),
        api('/nowcast/city?live=true').catch(() => null),
      ]);
      set({ dashboard, nowcast, isLive: true, lastUpdated: new Date(), liveError: null });
      return dashboard;
    } catch (error) {
      set(() => ({ isLive: false, liveError: error.message || 'Live risk feed unavailable' }));
      return get().dashboard;
    }
  },
  selectZone: (id) => set({ selectedZoneId: id }),
  selectedZone: () => get().dashboard.zones.find((zone) => zone.id === get().selectedZoneId) || get().dashboard.zones[0],
  setDashboard: (dashboard) => set({ dashboard }),
  setNowcast: (nowcast) => set({ nowcast }),
  isLive: false,
  lastUpdated: null,
  liveError: null,
}));

