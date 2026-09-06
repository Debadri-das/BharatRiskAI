import RiskMarker from './RiskMarker';
export default function RiskLayer({ zones, onSelect }) { return zones.map((zone) => <RiskMarker key={zone.id} zone={zone} onSelect={onSelect} />); }
