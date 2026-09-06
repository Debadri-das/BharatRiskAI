import { riskColor, number } from '../../utils/format';
import RiskBreakdown from './RiskBreakdown';
export default function RiskCard({ zone }) {
  return <section className="panel" style={{ padding: 16 }}>
    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}><div><h3 style={{ margin: 0 }}>{zone.name}</h3><p style={{ margin: '4px 0 12px', color: '#52645f' }}>Population exposed: {number(zone.population)}</p></div><b style={{ color: riskColor(zone.risk_category), fontSize: 28 }}>{zone.risk_score}</b></div>
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2,minmax(0,1fr))', gap: 8, marginBottom: 14 }}>
      <span>Category: <b>{zone.risk_category}</b></span><span>Rainfall: <b>{zone.rainfall_24h} mm</b></span><span>Elevation: <b>{zone.elevation} m</b></span><span>Drainage: <b>{zone.drainage_score}%</b></span><span>Flood history: <b>{zone.historical_flood_count}</b></span><span>Reports: <b>{zone.citizen_report_count}</b></span>
    </div>
    <RiskBreakdown zone={zone} />
  </section>;
}
