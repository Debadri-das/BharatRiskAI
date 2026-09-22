import { Activity, AlertTriangle, BarChart3, BookOpen, Network, RadioTower, Settings } from 'lucide-react';
import { useUiStore } from '../../store/uiStore';

const items = [
  ['Dashboard', Activity], ['Risk Analysis', BarChart3], ['Reports', AlertTriangle], ['Emergency Center', RadioTower], ['Mesh Simulator', Network], ['Settings', Settings], ['Project Details', BookOpen],
];

export default function Sidebar() {
  const { page, setPage } = useUiStore();
  return <aside className="sidebar-shell sidebar">
    <div className="sidebar-brand"><span className="sidebar-mark"><Activity size={18} /></span><div><h1>BHARATRISK</h1><p>AI OPERATIONS</p></div></div>
    <p className="sidebar-copy">Hyper-local weather intelligence for faster decisions.</p>
    <nav className="sidebar-nav">{items.map(([label, Icon]) => (
      <button key={label} onClick={() => setPage(label)} className={`btn ${page === label ? 'active' : ''}`} title={label}><Icon size={18} />{label}</button>
    ))}</nav>
    <div className="sidebar-footer"><span className="status-dot" /> System monitoring active</div>
  </aside>;
}
