import { useEmergencyStore } from '../../store/emergencyStore';
export default function OfflineBanner() {
  const { offlineForced } = useEmergencyStore();
  if (navigator.onLine && !offlineForced) return null;
  return <div className="panel" style={{ padding: 12, marginBottom: 12, background: '#fff7ed' }}>Offline mode active. Reports and SOS packets are queued locally and will sync when connectivity returns.</div>;
}
