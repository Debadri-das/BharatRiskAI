import { create } from 'zustand';
export const useEmergencyStore = create((set) => ({ meshConnected: true, offlineForced: false, setMeshConnected: (value) => set({ meshConnected: value }), setOfflineForced: (value) => set({ offlineForced: value }) }));
