import { useEffect, useState } from 'react';
import { AlertOctagon, Clock3, MapPin, RefreshCw, Users } from 'lucide-react';
import { getEmergencies } from '../../services/emergencyApi';

const statusClass = (status = '') => status.toLowerCase().replace(/\s+/g, '-');

export default function EmergencyList({ refreshKey = 0 }) {
  const [emergencies, setEmergencies] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  async function loadEmergencies() {
    setLoading(true);
    try {
      setEmergencies(await getEmergencies());
      setError(null);
    } catch {
      setError('Unable to load persisted SOS messages.');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    let active = true;
    loadEmergencies().then(() => { if (!active) setError(null); });
    return () => { active = false; };
  }, [refreshKey]);

  return <section className="records-panel panel">
    <div className="records-heading"><div><span className="section-kicker">RESPONSE QUEUE</span><h2>Persisted SOS messages</h2><p>Emergency requests stored in Supabase.</p></div><button className="icon-button light" onClick={loadEmergencies} title="Refresh SOS messages" aria-label="Refresh SOS messages"><RefreshCw size={16} /></button></div>
    {loading && <p className="records-empty">Loading emergency messages...</p>}
    {error && <p className="records-error">{error}</p>}
    {!loading && !error && emergencies.length === 0 && <p className="records-empty">No persisted SOS messages yet.</p>}
    <div className="record-list">{emergencies.map((item) => <article className="record-item sos-record" key={item.id || item.message_id}>
      <div className="record-icon sos"><AlertOctagon size={16} /></div><div className="record-body"><div className="record-topline"><strong>{item.emergency_type}</strong><span className={`record-badge ${statusClass(item.status)}`}>{item.status}</span></div><p><Users size={13} /> {item.people} people <MapPin size={13} /> {Number(item.latitude).toFixed(4)}, {Number(item.longitude).toFixed(4)}</p><small><Clock3 size={12} /> {item.created_at ? new Date(item.created_at).toLocaleString() : 'Recently received'} · {item.message_id}</small></div>
    </article>)}</div>
  </section>;
}
