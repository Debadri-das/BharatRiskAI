import { api } from './api';
export const submitReport = (payload) => api('/report', { method: 'POST', body: JSON.stringify(payload) });
export const getReports = () => api('/reports');
