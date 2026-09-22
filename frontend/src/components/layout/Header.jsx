import { Wifi, WifiOff } from 'lucide-react';
import { useRiskStore } from '../../store/riskStore';
import { Radio } from 'lucide-react';
import NotificationCenter from './NotificationCenter';

export default function Header() {
  const { dashboard, isLive, lastUpdated } = useRiskStore();
  const online = navigator.onLine;
  const updatedLabel = lastUpdated ? `Updated ${lastUpdated.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}` : 'Waiting for feed';
  return <header className="topbar">
    <div className="brand-lockup"><div className="eyebrow"><Radio size={14} /> LIVE OPERATIONS CONSOLE</div><h2>{dashboard.title}</h2><p>{dashboard.subtitle}</p></div>
    <div className="topbar-meta"><span className={`feed-status ${isLive ? 'live' : 'stale'}`}><span className="status-dot" />{isLive ? 'LIVE SATELLITE FEED' : 'FEED UNAVAILABLE'}</span><span className="updated-label">{updatedLabel}</span><span className="network-status">{online ? <><Wifi size={16} /> Online</> : <><WifiOff size={16} /> Offline</>}</span><NotificationCenter /></div>
  </header>;
}
