import { Activity, AlertTriangle, BarChart3, RadioTower, Settings, SlidersHorizontal } from 'lucide-react';
import { useUiStore } from '../../store/uiStore';
const items = [['Dashboard', Activity], ['Risk Analysis', BarChart3], ['Simulation', SlidersHorizontal], ['Reports', AlertTriangle], ['Emergency Center', RadioTower], ['Settings', Settings]];
export default function BottomNav() {
  const { page, setPage } = useUiStore();
  return <nav style={{ position: 'fixed', bottom: 0, left: 0, right: 0, display: 'grid', gridTemplateColumns: 'repeat(6,1fr)', background: '#14211d', zIndex: 1000 }} className="mobile-only">{items.map(([label, Icon]) => <button key={label} title={label} onClick={() => setPage(label)} style={{ color: page === label ? '#9ff0d4' : 'white', background: 'transparent', border: 0, padding: 10 }}><Icon size={20} /></button>)}</nav>;
}
