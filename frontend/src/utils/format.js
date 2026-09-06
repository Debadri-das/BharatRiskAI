export const riskCategory = (score) => (score <= 25 ? 'LOW' : score <= 50 ? 'MEDIUM' : score <= 75 ? 'HIGH' : 'CRITICAL');
export const riskColor = (category) => ({ LOW: '#2f855a', MEDIUM: '#d69e2e', HIGH: '#dd6b20', CRITICAL: '#c53030' }[category] || '#4a5568');
export const number = (value) => new Intl.NumberFormat('en-IN').format(Math.round(value || 0));
