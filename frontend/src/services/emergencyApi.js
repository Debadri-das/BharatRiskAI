import { api } from './api';
export const sendEmergency = (payload) => api('/emergency', { method: 'POST', body: JSON.stringify(payload) });
export const getEmergencies = () => api('/emergencies');
