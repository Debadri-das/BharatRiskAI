import { allQueued } from './indexedDB';
import { sendEmergency } from '../services/emergencyApi';
import { submitReport } from '../services/reportApi';

export async function syncQueued() {
  if (!navigator.onLine) return { synced: 0 };
  const items = await allQueued();
  let synced = 0;
  for (const item of items) {
    if (item.type === 'report') await submitReport(item.payload);
    if (item.type === 'emergency') await sendEmergency(item.payload);
    synced += 1;
  }
  return { synced };
}
