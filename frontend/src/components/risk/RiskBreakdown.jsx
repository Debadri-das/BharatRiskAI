export default function RiskBreakdown({ zone }) {
  return <div style={{ display: 'grid', gap: 8 }}>{Object.entries(zone.breakdown || {}).map(([key, value]) => (
    <div key={key}><div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13 }}><span>{key.replaceAll('_', ' ')}</span><b>{value}%</b></div><div style={{ height: 7, background: '#dfe8e4', borderRadius: 99 }}><div style={{ height: 7, width: `${value}%`, background: '#0f766e', borderRadius: 99 }} /></div></div>
  ))}</div>;
}
