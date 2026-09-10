import React from 'react';
import { CloudRain, Zap, Wind, Waves, Thermometer } from 'lucide-react';

const hazardBadgeStyle = (level) => {
  switch (level?.toUpperCase()) {
    case 'SEVERE':
    case 'CRITICAL':
    case 'RED':
      return { bg: '#fee2e2', text: '#991b1b', border: '#f87171' };
    case 'HIGH':
    case 'ORANGE':
      return { bg: '#ffedd5', text: '#c2410c', border: '#fb923c' };
    case 'MODERATE':
    case 'YELLOW':
      return { bg: '#fef9c3', text: '#854d0e', border: '#fde047' };
    default:
      return { bg: '#dcfce7', text: '#166534', border: '#86efac' };
  }
};

export default function MultiHazardMatrix({ nowcastData }) {
  if (!nowcastData) return null;

  const hazards = [
    {
      title: 'Rain Intensity',
      value: `${nowcastData.max_rain_rate_mm_hr || 0} mm/h`,
      level: (nowcastData.max_rain_rate_mm_hr || 0) >= 50 ? 'SEVERE' : (nowcastData.max_rain_rate_mm_hr || 0) >= 30 ? 'HIGH' : 'LOW',
      icon: CloudRain,
    },
    {
      title: 'Lightning Risk',
      value: nowcastData.lightning_risk || 'LOW',
      level: nowcastData.lightning_risk || 'LOW',
      icon: Zap,
    },
    {
      title: 'Wind & Squall',
      value: nowcastData.squall_risk || 'LOW',
      level: nowcastData.squall_risk || 'LOW',
      icon: Wind,
    },
    {
      title: 'Flash Flood Threat',
      value: `${nowcastData.max_flood_threat_score || 0}/100`,
      level: (nowcastData.max_flood_threat_score || 0) >= 75 ? 'CRITICAL' : (nowcastData.max_flood_threat_score || 0) >= 50 ? 'HIGH' : 'LOW',
      icon: Waves,
    },
    {
      title: 'Thunderstorm Prob',
      value: `${nowcastData.thunderstorm_prob || 0}%`,
      level: (nowcastData.thunderstorm_prob || 0) >= 70 ? 'HIGH' : (nowcastData.thunderstorm_prob || 0) >= 40 ? 'MODERATE' : 'LOW',
      icon: Thermometer,
    },
  ];

  return (
    <article className="panel" style={{ padding: 16, marginBottom: 14 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <h3 style={{ margin: 0, fontSize: 15, fontWeight: 700 }}>Multi-Hazard Threat Matrix</h3>
        <span style={{ fontSize: 11, color: '#657871' }}>AI Atmospheric Synthesis</span>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: 8 }}>
        {hazards.map((h) => {
          const Icon = h.icon;
          const badge = hazardBadgeStyle(h.level);
          return (
            <div
              key={h.title}
              style={{
                background: badge.bg,
                border: `1px solid ${badge.border}`,
                borderRadius: 8,
                padding: '10px 12px',
                display: 'flex',
                flexDirection: 'column',
                gap: 4,
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: 11, fontWeight: 600, color: badge.text }}>{h.title}</span>
                <Icon size={14} color={badge.text} />
              </div>
              <strong style={{ fontSize: 15, color: badge.text }}>{h.value}</strong>
              <small style={{ fontSize: 9, fontWeight: 800, textTransform: 'uppercase', color: badge.text }}>
                {h.level}
              </small>
            </div>
          );
        })}
      </div>
    </article>
  );
}
