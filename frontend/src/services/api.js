const API_BASE = import.meta.env.VITE_API_BASE || import.meta.env.VITE_API_URL || '/api';

// Standardized fetch with error handling
export const apiFetch = async (path, options = {}) => {
  const url = path.startsWith('http') ? path : `${API_BASE}${path.startsWith('/') ? '' : '/'}${path}`;
  const response = await fetch(url, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  });
  if (!response.ok) {
    const errorData = await response.text().catch(() => '');
    const message = errorData || `API ${response.status}`;
    throw new Error(`${response.status} - ${message}`);
  }
  return response.json();
};

export const api = apiFetch;
export default apiFetch;

// Dashboard endpoints
export const getDashboard = () => apiFetch('/dashboard');
export const getZones = () => apiFetch('/zones');
export const getRisk = (id) => apiFetch(`/risk/${id}`);
export const getConnectivity = () => apiFetch('/connectivity');

// Nowcast endpoints
export const getCitywideNowcast = (live = true) => apiFetch(`/nowcast/city?live=${live}`);
export const getZoneNowcast = (zoneId, live = true) => apiFetch(`/nowcast/zone/${zoneId}?live=${live}`);
export const getNowcastAlerts = (live = true) => apiFetch(`/nowcast/alerts?live=${live}`);

// Report endpoints
export const submitReport = (payload) => apiFetch('/report', {
  method: 'POST',
  body: JSON.stringify(payload),
});
export const getReports = () => apiFetch('/reports');

// Emergency endpoints
export const sendEmergency = (payload) => apiFetch('/emergency', {
  method: 'POST',
  body: JSON.stringify(payload),
});
export const getEmergencies = () => apiFetch('/emergencies');

// Recommendation endpoints
export const getRecommendations = (zoneId) => apiFetch(`/recommendations${zoneId ? `?zone_id=${zoneId}` : ''}`);
export const getResources = () => apiFetch('/resources');

// Geo/spatial endpoints
export const getSatelliteStatus = () => apiFetch('/satellite/status');
export const getLatestSatelliteScene = (zoneId, live = false) => apiFetch(`/satellite/latest/${zoneId}?live=${live}`);

