import { create } from 'zustand';
import { api } from '../services/api';
import { demoDashboard, demoNowcast } from '../services/demoData';

export const useRiskStore = create((set, get) => ({
  dashboard: demoDashboard(),
  nowcast: demoNowcast(),
  selectedZoneId: 1,
  load: async () => {
    try {
      const [dashboard, nowcast] = await Promise.all([
        api('/dashboard'),
        api('/nowcast/city?live=true').catch(() => null),
      ]);
      set((state) => ({
        dashboard,
        nowcast: nowcast || state.nowcast || demoNowcast(),
        isLive: true,
        lastUpdated: new Date(),
        liveError: null,
      }));
      return dashboard;
    } catch (error) {
      set((state) => ({
        isLive: false,
        nowcast: state.nowcast || demoNowcast(),
        liveError: error.message || 'Live risk feed unavailable',
      }));
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

