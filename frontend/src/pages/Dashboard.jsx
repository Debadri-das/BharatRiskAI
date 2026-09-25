import React, { useEffect, useMemo, useState } from 'react';
import { LocateFixed, MapPinned, RefreshCw, Search, ShieldAlert, Users, Waves, CloudRain } from 'lucide-react';
import RiskMap from '../components/map/RiskMap';
import CitizenReportForm from '../components/reports/CitizenReportForm';
import EmergencyForm from '../components/emergency/EmergencyForm';
import EarlyWarningBanner from '../components/nowcast/EarlyWarningBanner';
import NowcastTimeline from '../components/nowcast/NowcastTimeline';
import MultiHazardMatrix from '../components/nowcast/MultiHazardMatrix';
import ProbabilityGrid from '../components/nowcast/ProbabilityGrid';
import XaiTriggers from '../components/nowcast/XaiTriggers';
import TeamSection from '../components/common/TeamSection';
import { useRiskStore } from '../store/riskStore';
import { distanceKm } from '../utils/geo';
import { usePreferencesStore } from '../store/preferencesStore';

export default function Dashboard(){
  const dashboard = useRiskStore((state) => state.dashboard);
  const nowcast = useRiskStore((state) => state.nowcast);
  const isLive = useRiskStore((state) => state.isLive);
  const load = useRiskStore((state) => state.load);
  const [location, setLocation] = useState(null);
  const [locationState, setLocationState] = useState('requesting');
  const [selectedZoneId, setSelectedZoneId] = useState(null);
  const [locationQuery, setLocationQuery] = useState('');
  const locationSharing = usePreferencesStore((state) => state.locationSharing);

  useEffect(()=>{
    if (!locationSharing) { setLocation(null); setLocationState('disabled'); return undefined; }
    if (!navigator.geolocation) { setLocationState('unsupported'); return undefined; }
    const watcher = navigator.geolocation.watchPosition(
      ({ coords }) => { setLocation({ latitude: coords.latitude, longitude: coords.longitude, accuracy: coords.accuracy }); setLocationState('located'); },
      () => setLocationState('denied'),
      { enableHighAccuracy: true, maximumAge: 60000, timeout: 10000 },
    );
    return () => navigator.geolocation.clearWatch(watcher);
  },[locationSharing]);

  const nearestZone = useMemo(() => {
    if (!location || !dashboard.zones?.length) return null;
    return dashboard.zones.reduce((nearest, zone) => {
      const candidate = { ...zone, distance: distanceKm(location, zone) };
      return !nearest || candidate.distance < nearest.distance ? candidate : nearest;
    }, null);
  }, [dashboard.zones, location]);

  const selectedZone = useMemo(() => {
    if (selectedZoneId === null) return nearestZone || dashboard.zones?.[0];
    return dashboard.zones?.find((zone) => zone.id === selectedZoneId) || nearestZone || dashboard.zones?.[0];
  }, [dashboard.zones, nearestZone, selectedZoneId]);

  const selectedZoneNowcast = useMemo(() => {
    if (!nowcast?.zones_nowcast || !selectedZone) return null;
    const zn = nowcast.zones_nowcast.find((z) => z.zone_id === selectedZone.id);
    return zn?.nowcast || null;
  }, [nowcast, selectedZone]);

  const visibleZones = useMemo(() => {
    const query = locationQuery.trim().toLowerCase();
    return (dashboard.zones || []).filter((zone) => zone.name.toLowerCase().includes(query));
  }, [dashboard.zones, locationQuery]);

  function refresh(){ load(); }

  const primaryAlert = nowcast?.alerts?.[0] || {
    alert_level: nowcast?.overall_alert_level || 'ORANGE',
    primary_hazard: 'SEVERE CONVECTIVE DOWNPOUR & SQUALL',
    lead_time_minutes: nowcast?.earliest_lead_time_minutes || 35,
    advisory: 'Move to elevated ground, secure outdoor assets, keep communication lines open.',
  };

  return (
    <div className="dashboard-page">
      <section className="hero-strip">
        <div>
          <span className="section-kicker">AI-DRIVEN EARLY WARNING SYSTEM</span>
          <h1>Hyper-Local Severe Weather Nowcasting</h1>
          <p>Real-time convective radar extrapolation and 0–6 hour lead-time threat prediction for municipal disaster response.</p>
        </div>
        <button className="icon-button" onClick={refresh} title="Refresh live risk feed" aria-label="Refresh live risk feed">
          <RefreshCw size={18} />
        </button>
      </section>

      {/* Proactive Early Warning Alert Banner */}
      <EarlyWarningBanner
        alertLevel={primaryAlert.alert_level}
        primaryHazard={primaryAlert.primary_hazard}
        leadTimeMinutes={primaryAlert.lead_time_minutes}
        advisory={primaryAlert.advisory}
        zoneName={primaryAlert.zone_name || 'Metropolitan Risk Corridor'}
      />

      {/* Metric Cards */}
      <section className="metric-grid">
        <article className="metric-card metric-main">
          <div className="metric-icon"><ShieldAlert size={18} /></div>
          <span>Overall threat index</span>
          <strong>{dashboard.stats.overall_risk}<small>/100</small></strong>
          <em className={isLive ? 'live-copy' : ''}>{isLive ? 'Live Atmospheric Nowcast Feed' : 'Offline Convective Simulator'}</em>
        </article>
        <article className="metric-card">
          <div className="metric-icon amber"><CloudRain size={18} /></div>
          <span>Peak Predicted Rain Rate</span>
          <strong>{nowcast?.max_predicted_rain_rate_mm_hr || 58.4}<small> mm/h</small></strong>
          <em>{nowcast?.active_alerts_count || 3} zones under active alert</em>
        </article>
        <article className="metric-card">
          <div className="metric-icon coral"><Users size={18} /></div>
          <span>Exposed Population</span>
          <strong>{Number(dashboard.stats.population_at_risk).toLocaleString('en-IN')}</strong>
          <em>Across {dashboard.stats.critical_zones} critical wards</em>
        </article>
      </section>

      {/* 0-6h Nowcasting Timeline & Multi-Hazard Matrix */}
      {selectedZoneNowcast && (
        <NowcastTimeline timeline={selectedZoneNowcast.timeline} zoneName={selectedZone?.name} />
      )}

      {selectedZoneNowcast && (
        <MultiHazardMatrix nowcastData={selectedZoneNowcast} />
      )}

      {selectedZoneNowcast && (
        <ProbabilityGrid maps={selectedZoneNowcast.hazard_probability_maps} />
      )}

      {selectedZoneNowcast && (
        <XaiTriggers triggers={selectedZoneNowcast.xai_triggers} />
      )}

      {/* Live Map & Location Browser */}
      <section className="workspace-grid">
        <div className="map-panel panel">
          <div className="panel-heading">
            <div>
              <span className="section-kicker">RADAR & INUNDATION SURFACE</span>
              <h2>Hyper-Local Threat Zones</h2>
            </div>
            <span className="map-legend"><i className="legend-dot critical" /> Critical <i className="legend-dot high" /> High</span>
          </div>
          <div className="map-container">
            <RiskMap zones={dashboard.zones} location={location} selectedZoneId={selectedZone?.id} onZoneSelect={setSelectedZoneId} nowcastData={selectedZoneNowcast} />
          </div>
          <div className="location-browser">
            <div className="panel-heading">
              <h2><MapPinned size={18} /> Monitored Wards & Sectors</h2>
              <span>{dashboard.zones.length} locations</span>
            </div>
            <label className="search-field">
              <Search size={16} />
              <input value={locationQuery} onChange={(event) => setLocationQuery(event.target.value)} placeholder="Search a ward or locality" aria-label="Search monitored locations" />
            </label>
            <div className="location-list">
              {visibleZones.map((zone) => (
                <button className={`location-row ${selectedZone?.id === zone.id ? 'selected' : ''}`} key={zone.id} onClick={() => setSelectedZoneId(zone.id)}>
                  <span>
                    <strong>{zone.name}</strong>
                    <small>{zone.rainfall_24h} mm rain · {Number(zone.population).toLocaleString('en-IN')} people</small>
                  </span>
                  <b className={`risk-text ${zone.risk_category.toLowerCase()}`}>{zone.risk_score}</b>
                </button>
              ))}
              {visibleZones.length === 0 && <p className="empty-state">No monitored locations match that search.</p>}
            </div>
          </div>
        </div>

        <aside className="insight-column">
          <article className="location-card panel">
            <div className="panel-heading">
              <h2><LocateFixed size={18} /> {selectedZone ? 'Selected Ward' : 'Your Vicinity'}</h2>
              <span className="location-state">{selectedZone && nearestZone?.id === selectedZone.id ? 'GPS MATCH' : selectedZone ? 'MONITORED ZONE' : 'LOCATING'}</span>
            </div>
            {selectedZone ? (
              <>
                <div className="nearby-zone">
                  <strong>{selectedZone.name}</strong>
                  <span>{nearestZone?.id === selectedZone.id ? `${selectedZone.distance?.toFixed(1) || 0.8} km away` : 'Selected on map'}</span>
                </div>
                <div className={`risk-banner ${selectedZone.risk_category.toLowerCase()}`}>
                  <span>{nearestZone?.id === selectedZone.id ? 'Hyper-local risk' : 'Ward risk'}</span>
                  <strong>{selectedZone.risk_score}<small>/100</small></strong>
                  <b>{selectedZone.risk_category}</b>
                </div>
                <dl className="detail-list">
                  <div>
                    <dt>Rainfall 24h</dt>
                    <dd>{selectedZone.rainfall_24h} mm</dd>
                  </div>
                  <div>
                    <dt>Drainage</dt>
                    <dd>{selectedZone.drainage_score}/100</dd>
                  </div>
                  <div>
                    <dt>Elevation</dt>
                    <dd>{selectedZone.elevation} m</dd>
                  </div>
                </dl>
                {nearestZone && nearestZone.id !== selectedZone.id && (
                  <button className="text-button" onClick={() => setSelectedZoneId(nearestZone.id)}>
                    <LocateFixed size={14} /> Return to your vicinity
                  </button>
                )}
              </>
            ) : (
              <p className="empty-state">Allow location access to see the closest monitored ward.</p>
            )}
          </article>

          <article className="panel recommendations">
            <div className="panel-heading">
              <h2>Priority Response Directives</h2>
              <span>{dashboard.recommendations.length} directives</span>
            </div>
            {dashboard.recommendations.slice(0, 4).map((recommendation) => (
              <div className="recommendation" key={`${recommendation.priority}-${recommendation.action}`}>
                <span>{String(recommendation.priority).padStart(2, '0')}</span>
                <div>
                  <strong>{recommendation.action}</strong>
                  <p>{recommendation.reason}</p>
                </div>
              </div>
            ))}
          </article>
        </aside>
      </section>

      {/* Downstream Ground Intelligence & Emergency SOS */}
      <section className="forms-grid">
        <CitizenReportForm onSubmitted={refresh} />
        <EmergencyForm onSubmitted={refresh} />
      </section>

      {/* Team CaffineCoders */}
      <TeamSection />
    </div>
  );
}

