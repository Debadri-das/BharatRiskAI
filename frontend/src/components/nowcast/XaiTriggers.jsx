import React from 'react';

const groups = [
  ['moisture', 'Moisture fuel'],
  ['instability', 'Instability energy'],
  ['lift_and_structure', 'Lift and structure'],
  ['cloud_growth', 'Cloud growth'],
  ['flood_catalyst', 'Flood catalyst'],
];

export default function XaiTriggers({ triggers }) {
  if (!triggers) return null;
  return (
    <section className="panel" style={{ padding: 18, marginBottom: 14 }}>
      <div className="panel-heading">
        <div>
          <span className="section-kicker">EXPLAINABLE AI</span>
          <h2>Atmospheric triggers</h2>
        </div>
        <span style={{ color: '#657871', fontSize: 12 }}>IWV + IMDAA + DEM signals</span>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(145px, 1fr))', gap: 10 }}>
        {groups.map(([key, label]) => (
          <article key={key} style={{ background: '#f8faf9', padding: 10, borderRadius: 8 }}>
            <strong style={{ display: 'block', fontSize: 12 }}>{label}</strong>
            {Object.entries(triggers[key] || {}).map(([name, value]) => (
              <span key={name} style={{ display: 'block', color: '#657871', fontSize: 11, marginTop: 4 }}>
                {name.replaceAll('_', ' ')}: <b style={{ color: '#14211d' }}>{typeof value === 'number' ? value.toFixed(2) : value}</b>
              </span>
            ))}
          </article>
        ))}
      </div>
    </section>
  );
}