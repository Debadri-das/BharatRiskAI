import { api } from './api';

export const getCitywideNowcast = () => api('/nowcast/city?live=true');
export const getZoneNowcast = (zoneId) => api(`/nowcast/zone/${zoneId}?live=true`);
export const getNowcastAlerts = () => api('/nowcast/alerts?live=true');
