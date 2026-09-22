import React, { useEffect } from "react";
import { MapContainer, TileLayer, Popup, CircleMarker, useMap } from "react-leaflet";
import "leaflet/dist/leaflet.css";

function colorForCategory(cat){
  switch(cat){
    case 'CRITICAL': return '#7f1d1d';
    case 'HIGH': return '#b45309';
    case 'MEDIUM': return '#b7791f';
    default: return '#065f46';
  }
}

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
    map.fitBounds(bounds, { padding: [28, 28], maxZoom: 12, animate: false });
  }, [map, zones]);

  return null;
}

export default function RiskMap({ zones, location, selectedZoneId, onZoneSelect }){
  const center = zones && zones.length ? [zones[0].latitude, zones[0].longitude] : [22.57,88.36];
  return (
    <MapContainer center={center} zoom={12} style={{ height: '100%', width: '100%' }} scrollWheelZoom>
      <MapViewport zones={zones} />
      <TileLayer
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        attribution="&copy; OpenStreetMap contributors"
        eventHandlers={{ tileerror: () => console.warn('Map tiles could not be loaded') }}
      />
      {zones && zones.map(z => (
        <CircleMarker
          key={z.id}
          center={[z.latitude, z.longitude]}
          radius={8 + Math.min(18, Math.floor(z.risk_score/6))}
          pathOptions={{ color: selectedZoneId === z.id ? '#14211d' : colorForCategory(z.risk_category), fillColor: colorForCategory(z.risk_category), fillOpacity: 0.8, weight: selectedZoneId === z.id ? 4 : 2 }}
          eventHandlers={{ click: () => onZoneSelect?.(z.id) }}
        >
          <Popup>
            <div>
              <h4>{z.name}</h4>
              <div>Risk: {z.risk_score} ({z.risk_category})</div>
              <div>Rainfall 24h: {z.rainfall_24h} mm</div>
              <div>Elevation: {z.elevation} m</div>
              <div>Drainage score: {z.drainage_score}</div>
              <div>Population: {z.population}</div>
            </div>
          </Popup>
        </CircleMarker>
      ))}
      {location && <CircleMarker center={[location.latitude, location.longitude]} radius={7} pathOptions={{ color: '#0f766e', fillColor: '#5eead4', fillOpacity: 1, weight: 3 }}><Popup>Your current location</Popup></CircleMarker>}
    </MapContainer>
  )
}
