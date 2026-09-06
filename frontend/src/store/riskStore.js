import { create } from 'zustand';
import { demoDashboard } from '../services/demoData';
import { api } from '../services/api';

export const useRiskStore = create((set, get) => ({
  dashboard: demoDashboard(),
  selectedZoneId: 1,
  simulated: null,
  load: async () => {
    try {
      const dashboard = await api('/dashboard');
      set({ dashboard, isLive: true, lastUpdated: new Date(), liveError: null });
      return dashboard;
    } catch (error) {
      set((state) => ({ isLive: false, liveError: error.message || 'Live risk feed unavailable' }));
      return get().dashboard;
    }
  },
  selectZone: (id) => set({ selectedZoneId: id }),
  selectedZone: () => get().dashboard.zones.find((zone) => zone.id === get().selectedZoneId) || get().dashboard.zones[0],
  setDashboard: (dashboard) => set({ dashboard }),
  setSimulated: (simulated) => set({ simulated }),
  isLive: false,
  lastUpdated: null,
  liveError: null,
}));
