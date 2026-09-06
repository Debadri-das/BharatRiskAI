import { CircleMarker, Popup } from 'react-leaflet';
import { riskColor, number } from '../../utils/format';

export default function RiskMarker({ zone, onSelect }) {
  return <CircleMarker center={[zone.latitude, zone.longitude]} radius={10 + zone.risk_score / 8} pathOptions={{ color: riskColor(zone.risk_category), fillColor: riskColor(zone.risk_category), fillOpacity: 0.55 }} eventHandlers={{ click: () => onSelect(zone.id) }}>
    <Popup>
      <strong>{zone.name}</strong><br />Risk: {zone.risk_score} ({zone.risk_category})<br />Rainfall: {zone.rainfall_24h} mm<br />Drainage: {zone.drainage_score}%<br />Population: {number(zone.population)}
    </Popup>
  </CircleMarker>;
}
