import { Wifi, WifiOff } from 'lucide-react';
import { useEmergencyStore } from '../../store/emergencyStore';
import { useRiskStore } from '../../store/riskStore';
import { Radio } from 'lucide-react';

export default function Header() {
  const { dashboard, isLive, lastUpdated } = useRiskStore();
  const { meshConnected, offlineForced } = useEmergencyStore();
  const online = navigator.onLine && !offlineForced;
  const updatedLabel = lastUpdated ? `Updated ${lastUpdated.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}` : 'Waiting for feed';
  return <header className="topbar">
    <div className="brand-lockup"><div className="eyebrow"><Radio size={14} /> LIVE OPERATIONS CONSOLE</div><h2>{dashboard.title}</h2><p>{dashboard.subtitle}</p></div>
    <div className="topbar-meta"><span className={`feed-status ${isLive ? 'live' : 'stale'}`}><span className="status-dot" />{isLive ? 'LIVE RISK FEED' : 'LOCAL SNAPSHOT'}</span><span className="updated-label">{updatedLabel}</span><span className="network-status">{online ? (meshConnected ? <><Wifi size={16} /> Mesh linked</> : <><Wifi size={16} /> Online</>) : <><WifiOff size={16} /> Offline</>}</span></div>
  </header>;
}
