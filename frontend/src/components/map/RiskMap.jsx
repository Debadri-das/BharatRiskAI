import React, { useEffect, useMemo, useState } from "react";
import { MapContainer, TileLayer, Popup, CircleMarker, Rectangle, useMap, LayersControl } from "react-leaflet";
import "leaflet/dist/leaflet.css";

/* ── colour helpers ── */

function colorForCategory(cat) {
  switch (cat) {
    case 'CRITICAL': return '#7f1d1d';
    case 'HIGH': return '#b45309';
    case 'MEDIUM': return '#b7791f';
    default: return '#065f46';
  }
}

/** Map a 0‑1 probability to an RGBA hazard color (transparent→yellow→orange→red→dark‑red). */
function hazardColor(value) {
  const v = Math.max(0, Math.min(1, value));
  if (v < 0.15) return { fill: 'rgba(254,240,138,0.08)', border: 'transparent' };
  if (v < 0.35) return { fill: `rgba(253,186,53,${0.25 + v})`, border: 'rgba(253,186,53,0.3)' };
  if (v < 0.55) return { fill: `rgba(234,88,12,${0.35 + v * 0.5})`, border: 'rgba(234,88,12,0.4)' };
  if (v < 0.75) return { fill: `rgba(220,38,38,${0.45 + v * 0.4})`, border: 'rgba(220,38,38,0.5)' };
  return { fill: `rgba(127,29,29,${0.6 + v * 0.35})`, border: 'rgba(127,29,29,0.6)' };
}

/** Map an elevation (m) to a terrain color (low→green, mid→brown, high→grey). */
function elevationColor(elev, minElev, maxElev) {
  const range = maxElev - minElev || 1;
  const t = Math.max(0, Math.min(1, (elev - minElev) / range));
  if (t < 0.25) return 'rgba(16,185,129,0.35)';      // low: green (flood-prone)
  if (t < 0.5)  return 'rgba(180,183,55,0.3)';        // mid-low: olive
  if (t < 0.75) return 'rgba(180,115,55,0.3)';        // mid-high: brown
  return 'rgba(120,113,108,0.3)';                      // high: grey
}

/* ── sub-components ── */

function MapViewport({ zones }) {
  const map = useMap();
  useEffect(() => {
    const resizeObserver = new ResizeObserver(() => map.invalidateSize({ animate: false }));
    resizeObserver.observe(map.getContainer());
    map.invalidateSize({ animate: false });
    return () => resizeObserver.disconnect();
  }, [map]);

  useEffect(() => {
    if (!zones?.length) return;
    const bounds = zones.map((zone) => [zone.latitude, zone.longitude]);
    map.fitBounds(bounds, { padding: [28, 28], maxZoom: 13, animate: false });
  }, [map, zones]);

  return null;
}

/**
 * Renders the 16×16 hazard probability grid as colored rectangles on the map.
 * `grid` is a 2D array [rows][cols] of 0-1 probabilities.
 * The grid is geo-referenced to the bounding box of the monitored zones.
 */
function HazardGridOverlay({ grid, bounds }) {
  if (!grid || !bounds) return null;
  const { south, north, west, east } = bounds;
  const rows = grid.length;
  const cols = grid[0]?.length || 0;
  if (!rows || !cols) return null;

  const cellH = (north - south) / rows;
  const cellW = (east - west) / cols;

  return grid.flatMap((row, r) =>
    row.map((value, c) => {
      if (value < 0.08) return null; // skip near-zero cells for performance
      const { fill, border } = hazardColor(value);
      const cellSouth = north - (r + 1) * cellH;
      const cellNorth = north - r * cellH;
      const cellWest = west + c * cellW;
      const cellEast = west + (c + 1) * cellW;
      return (
        <Rectangle
          key={`h-${r}-${c}`}
          bounds={[[cellSouth, cellWest], [cellNorth, cellEast]]}
          pathOptions={{ color: border, fillColor: fill, fillOpacity: 1, weight: 0.5 }}
        >
          <Popup>
            <div style={{ fontSize: 12 }}>
              <strong>{Math.round(value * 100)}% probability</strong>
              <br />Grid cell [{r},{c}]
            </div>
          </Popup>
        </Rectangle>
      );
    })
  ).filter(Boolean);
}

/**
 * Renders DEM elevation context as colored rectangles around each zone,
 * showing terrain height variation to identify flood-prone low areas.
 */
function DEMOverlay({ zones }) {
  if (!zones?.length) return null;
  const elevations = zones.map(z => z.elevation || 0);
  const minElev = Math.min(...elevations);
  const maxElev = Math.max(...elevations);
  const RADIUS = 0.008; // ~0.8km rectangle around each zone point

  return zones.map(z => {
    const color = elevationColor(z.elevation || 0, minElev, maxElev);
    return (
      <Rectangle
        key={`dem-${z.id}`}
        bounds={[
          [z.latitude - RADIUS, z.longitude - RADIUS],
          [z.latitude + RADIUS, z.longitude + RADIUS],
        ]}
        pathOptions={{ color: 'transparent', fillColor: color, fillOpacity: 1, weight: 0 }}
      >
        <Popup>
          <div style={{ fontSize: 12 }}>
            <strong>{z.name}</strong>
            <br />Elevation: {z.elevation} m
            <br />Slope risk: {z.elevation <= (minElev + (maxElev - minElev) * 0.3) ? '⚠️ Low-lying (flood prone)' : '✓ Elevated'}
          </div>
        </Popup>
      </Rectangle>
    );
  });
}

/* ── legend ── */

function MapLegend({ activeLayer }) {
  return (
    <div style={{
      position: 'absolute', bottom: 10, left: 10, zIndex: 1000,
      background: 'rgba(255,255,255,0.95)', borderRadius: 8, padding: '8px 12px',
      fontSize: 11, boxShadow: '0 1px 4px rgba(0,0,0,0.15)', lineHeight: 1.6,
    }}>
      {activeLayer === 'hazard' && (
        <>
          <strong style={{ display: 'block', marginBottom: 4 }}>Hazard Probability</strong>
          <div style={{ display: 'flex', gap: 3, alignItems: 'center' }}>
            {[0.1, 0.3, 0.5, 0.7, 0.9].map(v => (
              <span key={v} style={{
                display: 'inline-block', width: 24, height: 12, borderRadius: 2,
                background: hazardColor(v).fill, border: `1px solid ${hazardColor(v).border}`,
              }} />
            ))}
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: '#666', marginTop: 2 }}>
            <span>Low</span><span>High</span>
          </div>
        </>
      )}
      {activeLayer === 'dem' && (
        <>
          <strong style={{ display: 'block', marginBottom: 4 }}>DEM Elevation</strong>
          <div style={{ display: 'flex', gap: 3, alignItems: 'center' }}>
            <span style={{ display: 'inline-block', width: 24, height: 12, borderRadius: 2, background: 'rgba(16,185,129,0.5)' }} />
            <span style={{ display: 'inline-block', width: 24, height: 12, borderRadius: 2, background: 'rgba(180,183,55,0.45)' }} />
            <span style={{ display: 'inline-block', width: 24, height: 12, borderRadius: 2, background: 'rgba(180,115,55,0.45)' }} />
            <span style={{ display: 'inline-block', width: 24, height: 12, borderRadius: 2, background: 'rgba(120,113,108,0.45)' }} />
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: '#666', marginTop: 2 }}>
            <span>Low (flood-prone)</span><span>High</span>
          </div>
        </>
      )}
    </div>
  );
}

/* ── main component ── */

export default function RiskMap({ zones, location, selectedZoneId, onZoneSelect, nowcastData }) {
  const center = zones && zones.length ? [zones[0].latitude, zones[0].longitude] : [22.57, 88.36];

  const [activeLayer, setActiveLayer] = useState('hazard');
  const [selectedHazard, setSelectedHazard] = useState('thunderstorms');
  const [selectedHorizon, setSelectedHorizon] = useState(0);

  // Compute bounding box of all zones with padding for the grid overlay
  const gridBounds = useMemo(() => {
    if (!zones?.length) return null;
    const lats = zones.map(z => z.latitude);
    const lons = zones.map(z => z.longitude);
    const PAD = 0.025; // ~2.5km padding
    return {
      south: Math.min(...lats) - PAD,
      north: Math.max(...lats) + PAD,
      west: Math.min(...lons) - PAD,
      east: Math.max(...lons) + PAD,
    };
  }, [zones]);

  // Extract the selected hazard grid from nowcast data
  const hazardGrid = useMemo(() => {
    return nowcastData?.hazard_probability_maps?.[selectedHazard]?.[selectedHorizon] || null;
  }, [nowcastData, selectedHazard, selectedHorizon]);

  const hazardLabels = { thunderstorms: '⛈ Thunderstorms', cloudbursts: '🌧 Cloudbursts', flash_floods: '🌊 Flash Floods' };
  const horizonHours = [2, 3, 4, 5, 6];

  return (
    <div style={{ position: 'relative', height: '100%', width: '100%' }}>
      {/* Layer & hazard controls */}
      <div style={{
        position: 'absolute', top: 10, right: 10, zIndex: 1000,
        background: 'rgba(255,255,255,0.95)', borderRadius: 8, padding: '8px 10px',
        fontSize: 11, boxShadow: '0 1px 4px rgba(0,0,0,0.15)', display: 'flex', flexDirection: 'column', gap: 6,
      }}>
        <div style={{ display: 'flex', gap: 4 }}>
          {[
            { key: 'hazard', label: '🔥 Hazard' },
            { key: 'dem', label: '⛰ DEM' },
            { key: 'zones', label: '📍 Zones' },
          ].map(opt => (
            <button
              key={opt.key}
              onClick={() => setActiveLayer(opt.key)}
              style={{
                padding: '3px 8px', borderRadius: 5, border: 'none', cursor: 'pointer', fontSize: 11, fontWeight: 600,
                background: activeLayer === opt.key ? '#14211d' : '#e5e7eb',
                color: activeLayer === opt.key ? '#fff' : '#374151',
              }}
            >
              {opt.label}
            </button>
          ))}
        </div>

        {activeLayer === 'hazard' && (
          <>
            <select
              value={selectedHazard}
              onChange={e => setSelectedHazard(e.target.value)}
              style={{ fontSize: 11, padding: '2px 4px', borderRadius: 4, border: '1px solid #d1d5db' }}
              aria-label="Select hazard type"
            >
              {Object.entries(hazardLabels).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
            <select
              value={selectedHorizon}
              onChange={e => setSelectedHorizon(Number(e.target.value))}
              style={{ fontSize: 11, padding: '2px 4px', borderRadius: 4, border: '1px solid #d1d5db' }}
              aria-label="Select forecast hour"
            >
              {horizonHours.map((h, i) => <option key={h} value={i}>+{h}h forecast</option>)}
            </select>
          </>
        )}
      </div>

      <MapLegend activeLayer={activeLayer} />

      <MapContainer center={center} zoom={12} style={{ height: '100%', width: '100%' }} scrollWheelZoom>
        <MapViewport zones={zones} />
        <TileLayer
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          attribution="&copy; OpenStreetMap contributors"
          eventHandlers={{ tileerror: () => console.warn('Map tiles could not be loaded') }}
        />

        {/* DEM Elevation Overlay */}
        {activeLayer === 'dem' && <DEMOverlay zones={zones} />}

        {/* Hazard Probability Grid Overlay */}
        {activeLayer === 'hazard' && hazardGrid && (
          <HazardGridOverlay grid={hazardGrid} bounds={gridBounds} />
        )}

        {/* Zone markers (always visible, but prominent only in 'zones' mode) */}
        {zones && zones.map(z => (
          <CircleMarker
            key={z.id}
            center={[z.latitude, z.longitude]}
            radius={activeLayer === 'zones' ? 8 + Math.min(18, Math.floor(z.risk_score / 6)) : 5}
            pathOptions={{
              color: selectedZoneId === z.id ? '#14211d' : colorForCategory(z.risk_category),
              fillColor: colorForCategory(z.risk_category),
              fillOpacity: activeLayer === 'zones' ? 0.8 : 0.5,
              weight: selectedZoneId === z.id ? 4 : (activeLayer === 'zones' ? 2 : 1),
            }}
            eventHandlers={{ click: () => onZoneSelect?.(z.id) }}
          >
            <Popup>
              <div>
                <h4 style={{ margin: '0 0 4px' }}>{z.name}</h4>
                <div>Risk: <strong>{z.risk_score}</strong> ({z.risk_category})</div>
                <div>Rainfall 24h: {z.rainfall_24h} mm</div>
                <div>Elevation: {z.elevation} m</div>
                <div>Drainage: {z.drainage_score}/100</div>
                <div>Population: {Number(z.population).toLocaleString('en-IN')}</div>
              </div>
            </Popup>
          </CircleMarker>
        ))}

        {location && (
          <CircleMarker center={[location.latitude, location.longitude]} radius={7}
            pathOptions={{ color: '#0f766e', fillColor: '#5eead4', fillOpacity: 1, weight: 3 }}>
            <Popup>Your current location</Popup>
          </CircleMarker>
        )}
      </MapContainer>
    </div>
  );
}
