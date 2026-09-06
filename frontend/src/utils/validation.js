export const hasLocation = (payload) => Number.isFinite(Number(payload.latitude)) && Number.isFinite(Number(payload.longitude));
