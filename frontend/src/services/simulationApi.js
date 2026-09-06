import { api } from './api';
export const postSimulation = (payload) => api('/simulation', { method: 'POST', body: JSON.stringify(payload) });
