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
  return {
    rainfall: 34, weekly_saturation: 14, low_elevation: 13, poor_drainage: 22, population_exposure: 12, history_and_reports: 5,
  };
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
    status: navigator.onLine ? 'ONLINE' : 'OFFLINE',
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
