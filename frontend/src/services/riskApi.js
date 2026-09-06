import { api } from './api';
export const getZones = () => api('/zones');
export const getRisk = (id) => api(`/risk/${id}`);
