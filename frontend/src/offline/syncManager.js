import { allQueued, clearItem } from './indexedDB';
import { sendEmergency } from '../services/emergencyApi';
import { submitReport } from '../services/reportApi';
import { useEmergencyStore } from '../store/emergencyStore';

export async function syncQueued() {
  const offlineForced = useEmergencyStore.getState().offlineForced;
  if (!navigator.onLine || offlineForced) return { synced: 0, reason: 'offline' };
  
  const items = await allQueued();
  let synced = 0;
  for (const item of items) {
    try {
      if (item.type === 'report' || item.payload?.water_level_cm !== undefined) {
        await submitReport(item.payload || item);
      } else if (item.type === 'emergency' || item.payload?.emergency_type !== undefined) {
        await sendEmergency(item.payload || item);
      }
      if (item.id) {
        await clearItem(item.id);
      }
      synced += 1;
    } catch (err) {
      console.warn('Failed to sync item:', item, err);
    }
  }
  return { synced, total: items.length };
}

