import { putQueued, allQueued } from './indexedDB';

export async function queueWhenOffline(type, payload, sender) {
  if (navigator.onLine) return sender(payload);
  await putQueued({ type, payload });
  return { queued: true, type, payload };
}

export async function queueSize() {
  try { return (await allQueued()).length; } catch { return 0; }
}
