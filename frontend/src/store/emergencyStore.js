import { create } from 'zustand';
export const useEmergencyStore = create((set) => ({ offlineForced: false, setOfflineForced: (value) => set({ offlineForced: value }) }));
