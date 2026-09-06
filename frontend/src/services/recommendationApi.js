import { api } from './api';
export const getRecommendations = (zoneId) => api(`/recommendations${zoneId ? `?zone_id=${zoneId}` : ''}`);
