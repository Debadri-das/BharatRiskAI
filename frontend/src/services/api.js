const API_BASE = import.meta.env.VITE_API_BASE || import.meta.env.VITE_API_URL || '/api';

export async function api(path, options = {}) {
  const url = path.startsWith('http') ? path : `${API_BASE}${path.startsWith('/') ? '' : '/'}${path}`;
  const response = await fetch(url, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  });
  if (!response.ok) throw new Error(`API ${response.status}: ${await response.text()}`);
  return response.json();
}

export default {
  getDashboard: () => api('/dashboard'),
  getZones: () => api('/zones'),
  getRisk: (id) => api(`/risk/${id}`),
  postSimulation: (payload) => api('/simulation', { method: 'POST', body: JSON.stringify(payload) }),
  postReport: (payload) => api('/report', { method: 'POST', body: JSON.stringify(payload) }),
  postEmergency: (payload) => api('/emergency', { method: 'POST', body: JSON.stringify(payload) }),
};

export { API_BASE };

