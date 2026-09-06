import { Activity, AlertTriangle, BarChart3, RadioTower, Settings, SlidersHorizontal } from 'lucide-react';
import { useUiStore } from '../../store/uiStore';

const items = [
  ['Dashboard', Activity], ['Risk Analysis', BarChart3], ['Simulation', SlidersHorizontal], ['Reports', AlertTriangle], ['Emergency Center', RadioTower], ['Settings', Settings],
];

export default function Sidebar() {
  const { page, setPage } = useUiStore();
  return <aside className="desktop-only" style={{ background: '#14211d', color: 'white', padding: 20 }}>
    <h1 style={{ fontSize: 24, margin: '0 0 4px', letterSpacing: 0 }}>BHARATRISK AI</h1>
    <p style={{ color: '#a7c7bd', marginTop: 0, lineHeight: 1.35 }}>Disaster Intelligence & Emergency Response Platform</p>
    <nav style={{ display: 'grid', gap: 8, marginTop: 24 }}>{items.map(([label, Icon]) => (
      <button key={label} onClick={() => setPage(label)} className="btn" style={{ display: 'flex', gap: 10, alignItems: 'center', justifyContent: 'flex-start', background: page === label ? '#0f766e' : 'transparent' }} title={label}><Icon size={18} />{label}</button>
    ))}</nav>
  </aside>;
}
