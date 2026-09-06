import { riskColor } from '../../utils/format';
const cats = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'];
export default function MapLegend() { return <div className="panel" style={{ position: 'absolute', right: 12, bottom: 12, zIndex: 500, padding: 10, display: 'grid', gap: 6 }}>{cats.map((cat) => <span key={cat} style={{ display: 'flex', alignItems: 'center', gap: 8 }}><i style={{ width: 12, height: 12, borderRadius: 99, background: riskColor(cat) }} />{cat}</span>)}</div>; }
