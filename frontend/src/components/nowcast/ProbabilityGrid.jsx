import React, { useMemo, useState } from 'react';

const labels = {
  thunderstorms: 'Thunderstorms',
  cloudbursts: 'Cloudbursts',
  flash_floods: 'Flash floods',
};

export default function ProbabilityGrid({ maps, layers }) {
  const [hazard, setHazard] = useState('thunderstorms');
  const [horizon, setHorizon] = useState(0);
  const values = maps?.[hazard]?.[horizon];
  const cells = useMemo(() => (values || []).flat(), [values]);

  if (!cells.length) return null;
  const selectedLayer = layers?.find((layer) => layer.hazard === hazard && layer.horizon_index === horizon);

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
          {(selectedLayer ? layers.filter((layer) => layer.hazard === hazard) : [2, 3, 4, 5, 6].map((hour, index) => ({ horizon_hours: hour, horizon_index: index }))).map((item) => <option key={item.horizon_index} value={item.horizon_index}>+{item.horizon_hours}h</option>)}
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
      <small style={{ display: 'block', marginTop: 8, color: '#657871' }}>{selectedLayer ? `Geospatial raster: ${selectedLayer.width}×${selectedLayer.height}, ${selectedLayer.crs}, bounds ${selectedLayer.bounds.west.toFixed(3)},${selectedLayer.bounds.south.toFixed(3)} to ${selectedLayer.bounds.east.toFixed(3)},${selectedLayer.bounds.north.toFixed(3)}.` : 'Probability grid metadata is unavailable; values are shown without geographic placement.'}</small>
    </section>
  );
}
