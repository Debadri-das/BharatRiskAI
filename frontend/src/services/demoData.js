import { riskCategory } from '../utils/format';

const zones = [
  ['Zone 17 - Dhapa Wetlands', 22.546, 88.438, 186, 512, 4.2, 32, 18500, 41000, 12, 3.1],
  ['Zone 08 - Kalighat', 22.522, 88.343, 154, 448, 8.5, 42, 23600, 38500, 8, 2.4],
  ['Zone 04 - Salt Lake Sector V', 22.575, 88.433, 138, 390, 6.8, 51, 17500, 32000, 6, 3.8],
  ['Zone 12 - Howrah Maidan', 22.589, 88.31, 168, 470, 5.5, 38, 28200, 46000, 10, 2.9],
  ['Zone 21 - Behala', 22.499, 88.31, 142, 410, 7.2, 45, 21400, 39800, 7, 4.2],
  ['Zone 02 - Esplanade', 22.567, 88.352, 126, 345, 10.5, 61, 30800, 27500, 5, 1.8],
  ['Zone 25 - Rajarhat', 22.623, 88.48, 118, 310, 9.8, 64, 12200, 24000, 3, 5.2],
  ['Zone 31 - Tollygunge', 22.496, 88.349, 132, 370, 11, 58, 19100, 30000, 4, 3.6],
];

export function score(zone) {
  return Math.round(Math.min(100,
    Math.min(zone.rainfall_24h / 220, 1) * 35 +
    Math.min(zone.rainfall_7d / 650, 1) * 15 +
    Math.max(0, (20 - zone.elevation) / 20) * 15 +
    Math.max(0, (100 - zone.drainage_score) / 100) * 20 +
    Math.min(zone.population_density / 32000, 1) * 10 +
    Math.min((zone.historical_flood_count * 2 + zone.citizen_report_count * 5) / 40, 1) * 5) * 10) / 10;
}

export function breakdown(zone) {
  const contributions = {
    rainfall: Math.min(zone.rainfall_24h / 220, 1) * 35,
    weekly_saturation: Math.min(zone.rainfall_7d / 650, 1) * 15,
    low_elevation: Math.max(0, (20 - zone.elevation) / 20) * 15,
    poor_drainage: Math.max(0, (100 - zone.drainage_score) / 100) * 20,
    population_exposure: Math.min(zone.population_density / 32000, 1) * 10,
    history_and_reports: Math.min((zone.historical_flood_count * 2 + zone.citizen_report_count * 5) / 40, 1) * 5,
  };
  const total = Object.values(contributions).reduce((sum, value) => sum + value, 0) || 1;
  return Object.fromEntries(Object.entries(contributions).map(([key, value]) => [key, Math.round(value * 1000 / total) / 10]));
}

export function demoZones() {
  return zones.map((row, index) => {
    const zone = {
      id: index + 1, name: row[0], latitude: row[1], longitude: row[2], rainfall_24h: row[3], rainfall_7d: row[4],
      elevation: row[5], drainage_score: row[6], population_density: row[7], population: row[8],
      historical_flood_count: row[9], citizen_report_count: 0, area_km2: row[10],
    };
    zone.risk_score = score(zone); zone.risk_category = riskCategory(zone.risk_score); zone.breakdown = breakdown(zone);
    return zone;
  }).sort((a, b) => b.risk_score - a.risk_score);
}

export function recommendations(zone = demoZones()[0]) {
  return [
    { priority: 1, action: 'issue evacuation alert', resource_type: 'emergency_personnel', quantity: 1, reason: `${zone.name} is ${zone.risk_category} with ${zone.population.toLocaleString('en-IN')} people exposed.` },
    { priority: 2, action: 'deploy rescue team', resource_type: 'rescue_team', quantity: 3, reason: 'Low elevation, heavy rainfall, and citizen intelligence increase rescue urgency.' },
    { priority: 3, action: 'deploy boat', resource_type: 'boat', quantity: 3, reason: 'Flooded road links may block ground access.' },
    { priority: 4, action: 'deploy water pump', resource_type: 'water_pump', quantity: 4, reason: 'Drainage efficiency is below safe operating threshold.' },
    { priority: 5, action: 'open shelter', resource_type: 'shelter', quantity: 1, reason: 'Shelter capacity should be ready before evacuation begins.' },
  ];
}

export function demoDashboard() {
  const dz = demoZones();
  const overall = Math.round(dz.reduce((sum, z) => sum + z.risk_score, 0) / dz.length);
  return {
    title: 'BHARATRISK AI',
    subtitle: 'Disaster Intelligence & Emergency Response Platform',
    status: typeof navigator !== 'undefined' && navigator.onLine ? 'ONLINE' : 'OFFLINE',
    stats: {
      overall_risk: overall,
      critical_zones: dz.filter((z) => z.risk_category === 'CRITICAL').length,
      population_at_risk: dz.filter((z) => z.risk_score >= 51).reduce((sum, z) => sum + z.population, 0),
      active_alerts: dz.filter((z) => z.risk_score >= 76).length,
      pending_sos: 0,
    },
    zones: dz,
    recommendations: recommendations(dz[0]),
    reports: [{ id: 1, zone_id: 1, severity: 'HIGH', water_level_cm: 48, description: 'Water above footpath near Dhapa connector.', created_at: new Date().toISOString() }],
    emergencies: [],
    risk_trend: [{ time: '06:00', risk: 52 }, { time: '09:00', risk: 61 }, { time: '12:00', risk: overall }, { time: '15:00', risk: 77 }, { time: '18:00', risk: 84 }],
  };
}

export function demoNowcast() {
  const dz = demoZones();
  const generateGrid = (baseProb) => {
    return Array.from({ length: 5 }, (_, horizon) => {
      const decay = Math.max(0.2, 1 - horizon * 0.15);
      return Array.from({ length: 16 }, (_, r) =>
        Array.from({ length: 16 }, (_, c) => {
          const dist = Math.sqrt((r - 7.5) ** 2 + (c - 7.5) ** 2) / 10;
          return Math.round(Math.max(0.05, Math.min(0.95, baseProb * decay * (1 - dist * 0.5))) * 100) / 100;
        })
      );
    });
  };

  const zones_nowcast = dz.map((zone) => {
    const isCritical = zone.risk_category === 'CRITICAL';
    const isHigh = zone.risk_category === 'HIGH';
    const baseRain = isCritical ? 68.2 : isHigh ? 38.0 : 14.0;
    const baseProb = isCritical ? 0.88 : isHigh ? 0.62 : 0.25;

    const maps = {
      thunderstorms: generateGrid(baseProb),
      cloudbursts: generateGrid(baseProb * 0.85),
      flash_floods: generateGrid(baseProb * 0.9),
    };

    const bbox = [zone.longitude - 0.1, zone.latitude - 0.1, zone.longitude + 0.1, zone.latitude + 0.1];
    const probability_layers = [];
    ['thunderstorms', 'cloudbursts', 'flash_floods'].forEach((hazard) => {
      [2, 3, 4, 5, 6].forEach((hours, idx) => {
        probability_layers.push({
          id: `${hazard}-${idx}`,
          hazard,
          horizon_index: idx,
          horizon_hours: hours,
          type: 'raster',
          crs: 'EPSG:4326',
          bounds: { west: bbox[0], south: bbox[1], east: bbox[2], north: bbox[3] },
          width: 16,
          height: 16,
          values: maps[hazard][idx],
        });
      });
    });

    return {
      zone_id: zone.id,
      zone_name: zone.name,
      status: 'READY',
      nowcast: {
        status: 'READY',
        alert_level: isCritical ? 'RED' : isHigh ? 'ORANGE' : 'YELLOW',
        primary_hazard: isCritical ? 'CLOUDBURST / EXTREME DOWNPOUR' : isHigh ? 'SEVERE THUNDERSTORM' : 'MODERATE SHOWERS',
        lead_time_minutes: isCritical ? 120 : 180,
        peak_interval: '2h',
        max_rain_rate_mm_hr: baseRain,
        max_flood_threat_score: isCritical ? 85.0 : 62.0,
        thunderstorm_prob: Math.round(baseProb * 100),
        lightning_risk: isCritical ? 'HIGH' : 'MODERATE',
        squall_risk: isCritical ? 'HIGH' : 'LOW',
        advisory: isCritical ? 'Take immediate action. Move to higher ground.' : 'Be prepared for sudden convective showers.',
        timeline: [
          { interval: '2h', rain_rate_mm_hr: baseRain, radar_dbz: 52, wind_gust_kmh: 62, flood_threat_score: 82, thunderstorm_prob: Math.round(baseProb * 100), confidence: 0.92 },
          { interval: '3h', rain_rate_mm_hr: Math.round(baseRain * 0.8), radar_dbz: 46, wind_gust_kmh: 50, flood_threat_score: 72, thunderstorm_prob: Math.round(baseProb * 80), confidence: 0.88 },
          { interval: '4h', rain_rate_mm_hr: Math.round(baseRain * 0.6), radar_dbz: 38, wind_gust_kmh: 38, flood_threat_score: 58, thunderstorm_prob: Math.round(baseProb * 60), confidence: 0.84 },
          { interval: '5h', rain_rate_mm_hr: Math.round(baseRain * 0.4), radar_dbz: 28, wind_gust_kmh: 28, flood_threat_score: 44, thunderstorm_prob: Math.round(baseProb * 45), confidence: 0.80 },
          { interval: '6h', rain_rate_mm_hr: Math.round(baseRain * 0.25), radar_dbz: 20, wind_gust_kmh: 20, flood_threat_score: 30, thunderstorm_prob: Math.round(baseProb * 30), confidence: 0.76 },
        ],
        hazard_probability_maps: maps,
        map_shape: [5, 16, 16],
        probability_layers,
        xai_triggers: {
          moisture: { iwv: 54.2, attribution: 0.28, trigger: 'Critical moisture accumulation (>50 mm IWV)' },
          instability: { cape: 2850.0, attribution: 0.34, trigger: 'Severe convective instability (CAPE >2500 J/kg)' },
          lift_and_structure: { cape: 2850.0, attribution: 0.18, trigger: 'Low-level convergence trigger' },
          cloud_growth: { ctt_drop_rate: 4.8, attribution: 0.22, trigger: 'Explosive CTT cooling (-4.8°C/15min)' },
          flood_catalyst: { elevation_m: zone.elevation, attribution: 0.25, trigger: 'Low elevation basin runoff' },
        },
      },
    };
  });

  return {
    city: 'Kolkata Metropolitan Area',
    overall_alert_level: 'RED',
    earliest_lead_time_minutes: 120,
    max_predicted_rain_rate_mm_hr: 68.2,
    active_alerts_count: 3,
    status: 'READY',
    alerts: [
      {
        zone_id: 1,
        zone_name: 'Zone 17 - Dhapa Wetlands',
        alert_level: 'RED',
        primary_hazard: 'CLOUDBURST / EXTREME DOWNPOUR',
        lead_time_minutes: 120,
        peak_interval: '2h',
        rain_rate_mm_hr: 68.2,
        advisory: 'Take immediate action. Move to higher ground.',
      },
    ],
    zones_nowcast,
  };
}

