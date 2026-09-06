import { useState } from 'react';
import SOSButton from './SOSButton';
import { queueWhenOffline } from '../../offline/offlineQueue';
import { sendEmergency } from '../../services/emergencyApi';
import { sendViaBridge } from '../../mesh/meshBridge';

export default function EmergencyForm({ onRoute }) {
  const [form, setForm] = useState({ emergency_type: 'TRAPPED', latitude: 22.546, longitude: 88.438, people: 4, vulnerable: ['elderly'] });
  const [result, setResult] = useState(null);
  async function send() {
    const route = await sendViaBridge({ ...form, priority: 'CRITICAL' });
    onRoute(route);
    setResult(await queueWhenOffline('emergency', form, sendEmergency));
  }
  return <section className="panel" style={{ padding: 16, display: 'grid', gap: 12, justifyItems: 'center' }}><SOSButton onClick={send} /><select value={form.emergency_type} onChange={(e) => setForm({ ...form, emergency_type: e.target.value })}><option>TRAPPED</option><option>MEDICAL</option><option>EVACUATION</option></select><input value={form.people} onChange={(e) => setForm({ ...form, people: Number(e.target.value) })} /><button className="btn" onClick={send}>Send Demo SOS</button>{result && <small>{result.queued ? 'SOS queued locally and routed over mesh simulator.' : `Emergency received: ${result.message_id}`}</small>}</section>;
}
