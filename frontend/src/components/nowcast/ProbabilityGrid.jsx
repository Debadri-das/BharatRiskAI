import React, { useMemo, useState } from 'react';

const labels = {
  thunderstorms: 'Thunderstorms',
  cloudbursts: 'Cloudbursts',
  flash_floods: 'Flash floods',
};

export default function ProbabilityGrid({ maps }) {
  const [hazard, setHazard] = useState('thunderstorms');
  const [horizon, setHorizon] = useState(0);
  const values = maps?.[hazard]?.[horizon];
  const cells = useMemo(() => (values || []).flat(), [values]);

  if (!cells.length) return null;

  return (
    <section className="panel" style={{ padding: 18, marginBottom: 14 }}>
      <div className="panel-heading">
        <div>
          <span className="section-kicker">SPATIOTEMPORAL PROBABILITY SURFACE</span>
          <h2>MTL hazard map</h2>
        </div>
        <select value={hazard} onChange={(event) => setHazard(event.target.value)} aria-label="Select hazard probability map">
          {Object.keys(labels).map((key) => <option key={key} value={key}>{labels[key]}</option>)}
        </select>
        <select value={horizon} onChange={(event) => setHorizon(Number(event.target.value))} aria-label="Select forecast horizon">
          {[2, 3, 4, 5, 6].map((hour, index) => <option key={hour} value={index}>+{hour}h</option>)}
        </select>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: `repeat(${values[0].length}, 1fr)`, gap: 2, aspectRatio: '1', maxWidth: 360 }}>
        {cells.map((value, index) => (
          <span
            key={`${hazard}-${index}`}
            title={`${Math.round(value * 100)}% probability`}
            style={{ backgroundColor: `rgba(190, 38, 48, ${Math.max(0.08, value)})`, minWidth: 0 }}
          />
        ))}
      </div>
      <small style={{ display: 'block', marginTop: 8, color: '#657871' }}>Probability intensity from the shared satellite and thermodynamic feature surface.</small>
    </section>
  );
}