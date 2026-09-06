import React, { useEffect, useMemo, useState } from 'react';
import { LocateFixed, MapPinned, RefreshCw, Search, ShieldAlert, Users, Waves } from 'lucide-react';
import RiskMap from '../components/map/RiskMap';
import CitizenReportForm from '../components/reports/CitizenReportForm';
import EmergencyForm from '../components/emergency/EmergencyForm';
import { useRiskStore } from '../store/riskStore';
import { distanceKm } from '../utils/geo';

export default function Dashboard(){
  const dashboard = useRiskStore((state) => state.dashboard);
  const isLive = useRiskStore((state) => state.isLive);
  const load = useRiskStore((state) => state.load);
  const [location, setLocation] = useState(null);
  const [locationState, setLocationState] = useState('requesting');
  const [selectedZoneId, setSelectedZoneId] = useState(null);
  const [locationQuery, setLocationQuery] = useState('');

  useEffect(()=>{
    if (!navigator.geolocation) { setLocationState('unsupported'); return undefined; }
    const watcher = navigator.geolocation.watchPosition(
      ({ coords }) => { setLocation({ latitude: coords.latitude, longitude: coords.longitude, accuracy: coords.accuracy }); setLocationState('located'); },
      () => setLocationState('denied'),
      { enableHighAccuracy: true, maximumAge: 60000, timeout: 10000 },
    );
    return () => navigator.geolocation.clearWatch(watcher);
  },[]);

  const nearestZone = useMemo(() => {
    if (!location || !dashboard.zones?.length) return null;
    return dashboard.zones.reduce((nearest, zone) => {
      const candidate = { ...zone, distance: distanceKm(location, zone) };
      return !nearest || candidate.distance < nearest.distance ? candidate : nearest;
    }, null);
  }, [dashboard.zones, location]);

  const selectedZone = useMemo(() => {
    if (selectedZoneId === null) return nearestZone;
    return dashboard.zones.find((zone) => zone.id === selectedZoneId) || nearestZone;
  }, [dashboard.zones, nearestZone, selectedZoneId]);

  const visibleZones = useMemo(() => {
    const query = locationQuery.trim().toLowerCase();
    return (dashboard.zones || []).filter((zone) => zone.name.toLowerCase().includes(query));
  }, [dashboard.zones, locationQuery]);

  function refresh(){ load(); }

  return (
    <div className="dashboard-page">
      <section className="hero-strip"><div><span className="section-kicker">SITUATIONAL AWARENESS</span><h1>Know what is changing near you.</h1><p>Live risk scores from the connected operations feed, matched to your current position when permission is available.</p></div><button className="icon-button" onClick={refresh} title="Refresh live risk feed" aria-label="Refresh live risk feed"><RefreshCw size={18} /></button></section>
      <section className="metric-grid"><article className="metric-card metric-main"><div className="metric-icon"><ShieldAlert size={18} /></div><span>Overall threat index</span><strong>{dashboard.stats.overall_risk}<small>/100</small></strong><em className={isLive ? 'live-copy' : ''}>{isLive ? 'Streaming from backend' : 'Using last known snapshot'}</em></article><article className="metric-card"><div className="metric-icon amber"><Waves size={18} /></div><span>Critical zones</span><strong>{dashboard.stats.critical_zones}</strong><em>{dashboard.stats.active_alerts} active alerts</em></article><article className="metric-card"><div className="metric-icon coral"><Users size={18} /></div><span>People exposed</span><strong>{Number(dashboard.stats.population_at_risk).toLocaleString('en-IN')}</strong><em>Across monitored zones</em></article></section>
      <section className="workspace-grid"><div className="map-panel panel"><div className="panel-heading"><div><span className="section-kicker">LIVE MAP</span><h2>Threat surface</h2></div><span className="map-legend"><i className="legend-dot critical" /> Critical <i className="legend-dot high" /> High</span></div><div className="map-container"><RiskMap zones={dashboard.zones} location={location} selectedZoneId={selectedZone?.id} onZoneSelect={setSelectedZoneId} /></div><div className="location-browser"><div className="panel-heading"><h2><MapPinned size={18} /> Monitored locations</h2><span>{dashboard.zones.length} zones</span></div><label className="search-field"><Search size={16} /><input value={locationQuery} onChange={(event) => setLocationQuery(event.target.value)} placeholder="Search a zone or city area" aria-label="Search monitored locations" /></label><div className="location-list">{visibleZones.map((zone) => <button className={`location-row ${selectedZone?.id === zone.id ? 'selected' : ''}`} key={zone.id} onClick={() => setSelectedZoneId(zone.id)}><span><strong>{zone.name}</strong><small>{zone.rainfall_24h} mm rain · {Number(zone.population).toLocaleString('en-IN')} people</small></span><b className={`risk-text ${zone.risk_category.toLowerCase()}`}>{zone.risk_score}</b></button>)}{visibleZones.length === 0 && <p className="empty-state">No monitored locations match that search.</p>}</div></div></div><aside className="insight-column"><article className="location-card panel"><div className="panel-heading"><h2><LocateFixed size={18} /> {selectedZone ? 'Selected location' : 'Your vicinity'}</h2><span className="location-state">{selectedZone && nearestZone?.id === selectedZone.id ? 'GPS MATCH' : selectedZone ? 'MONITORED ZONE' : locationState === 'denied' ? 'PERMISSION NEEDED' : 'LOCATING'}</span></div>{selectedZone ? <><div className="nearby-zone"><strong>{selectedZone.name}</strong><span>{nearestZone?.id === selectedZone.id ? `${selectedZone.distance.toFixed(1)} km away` : 'Selected on map'}</span></div><div className={`risk-banner ${selectedZone.risk_category.toLowerCase()}`}><span>{nearestZone?.id === selectedZone.id ? 'Local risk' : 'Location risk'}</span><strong>{selectedZone.risk_score}<small>/100</small></strong><b>{selectedZone.risk_category}</b></div><dl className="detail-list"><div><dt>Rainfall, 24h</dt><dd>{selectedZone.rainfall_24h} mm</dd></div><div><dt>Drainage score</dt><dd>{selectedZone.drainage_score}/100</dd></div><div><dt>Population</dt><dd>{Number(selectedZone.population).toLocaleString('en-IN')}</dd></div></dl>{nearestZone && nearestZone.id !== selectedZone.id && <button className="text-button" onClick={() => setSelectedZoneId(nearestZone.id)}><LocateFixed size={14} /> Return to your vicinity</button>}</> : <p className="empty-state">Allow location access to see the closest monitored zone and local threat details.</p>}</article><article className="panel recommendations"><div className="panel-heading"><h2>Priority actions</h2><span>{dashboard.recommendations.length} signals</span></div>{dashboard.recommendations.slice(0, 4).map((recommendation) => <div className="recommendation" key={`${recommendation.priority}-${recommendation.action}`}><span>{String(recommendation.priority).padStart(2, '0')}</span><div><strong>{recommendation.action}</strong><p>{recommendation.reason}</p></div></div>)}</article></aside></section>
      <section className="forms-grid"><CitizenReportForm onSubmitted={refresh} /><EmergencyForm onSubmitted={refresh} /></section>
    </div>
  )
}
