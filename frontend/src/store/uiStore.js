import { create } from 'zustand';
export const useUiStore = create((set) => ({ page: 'Dashboard', setPage: (page) => set({ page }) }));
