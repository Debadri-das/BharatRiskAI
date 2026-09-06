export default function RecommendationPanel({ recommendations }) {
  return <section className="panel" style={{ padding: 16 }}><h3 style={{ marginTop: 0 }}>AI Action Recommendations</h3><div style={{ display: 'grid', gap: 10 }}>{(recommendations || []).map((rec, index) => <div key={`${rec.action}-${index}`} style={{ borderLeft: '4px solid #0f766e', paddingLeft: 10 }}><b>Priority {rec.priority}: {rec.action}</b><div>{rec.quantity} x {rec.resource_type}</div><p style={{ margin: '4px 0', color: '#52645f' }}>{rec.reason}</p></div>)}</div></section>;
}
