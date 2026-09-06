const BASE = (import.meta.env.VITE_API_URL) ? import.meta.env.VITE_API_URL : '';

async function getJson(path){
  const res = await fetch(BASE + path);
  if(!res.ok) throw new Error(await res.text());
  return res.json();
}

export default {
  getDashboard: () => getJson('/api/dashboard'),
  getZones: () => getJson('/api/zones'),
  getRisk: (id) => getJson(`/api/risk/${id}`),
  postSimulation: (payload) => fetch('/api/simulation', {method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(payload)}).then(r=>r.json()),
  postReport: (payload) => fetch('/api/report', {method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(payload)}).then(r=>r.json()),
  postEmergency: (payload) => fetch('/api/emergency', {method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(payload)}).then(r=>r.json()),
}
const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000/api';

export async function api(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  });
  if (!response.ok) throw new Error(`API ${response.status}: ${await response.text()}`);
  return response.json();
}

export { API_BASE };
