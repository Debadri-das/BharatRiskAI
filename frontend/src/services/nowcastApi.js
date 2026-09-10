import { api } from './api';

export const getCitywideNowcast = (live = false) => api(`/nowcast/city${live ? '?live=true' : ''}`);
export const getZoneNowcast = (zoneId, live = false) => api(`/nowcast/zone/${zoneId}${live ? '?live=true' : ''}`);
export const getNowcastAlerts = (live = false) => api(`/nowcast/alerts${live ? '?live=true' : ''}`);
export const simulateNowcastStorm = (payload) => api('/nowcast/simulate', {
  method: 'POST',
  body: JSON.stringify(payload),
});
