import { create } from 'zustand';

const storedPreferences = (() => {
  try {
    return JSON.parse(localStorage.getItem('bharatrisk-preferences') || '{}');
  } catch {
    return {};
  }
})();

export const usePreferencesStore = create((set, get) => ({
  profile: storedPreferences.profile || { name: 'Field operator', role: 'Response coordinator' },
  darkMode: Boolean(storedPreferences.darkMode),
  locationSharing: storedPreferences.locationSharing !== false,
  alertSounds: storedPreferences.alertSounds !== false,
  save: (changes) => {
    const next = { ...get(), ...changes };
    const preferences = {
      profile: next.profile,
      darkMode: next.darkMode,
      locationSharing: next.locationSharing,
      alertSounds: next.alertSounds,
    };
    localStorage.setItem('bharatrisk-preferences', JSON.stringify(preferences));
    set(changes);
  },
}));
