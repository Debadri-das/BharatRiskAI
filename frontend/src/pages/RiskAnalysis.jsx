import RiskCard from '../components/risk/RiskCard';
import { useRiskStore } from '../store/riskStore';
export default function RiskAnalysis() { const { dashboard, selectedZone, selectZone } = useRiskStore(); return <div style={{ display: 'grid', gridTemplateColumns: '280px 1fr', gap: 16 }}><section className="panel" style={{ padding: 12 }}>{dashboard.zones.map((z) => <button className="btn secondary" key={z.id} onClick={() => selectZone(z.id)} style={{ width: '100%', marginBottom: 8 }}>{z.name} - {z.risk_score}</button>)}</section><RiskCard zone={selectedZone()} /></div>; }
