import React from 'react';
import { AlertTriangle, Clock, CloudLightning, ShieldAlert, Waves, Wind } from 'lucide-react';

const alertThemes = {
  RED: {
    bg: 'linear-gradient(135deg, #7f1d1d, #991b1b)',
    border: '#f87171',
    badge: '#ef4444',
    icon: ShieldAlert,
    label: 'RED ALERT · IMMEDIATE ACTION REQUIRED',
  },
  ORANGE: {
    bg: 'linear-gradient(135deg, #9a3412, #c2410c)',
    border: '#fb923c',
    badge: '#f97316',
    icon: AlertTriangle,
    label: 'ORANGE ALERT · SEVERE WEATHER EXPECTED',
  },
  YELLOW: {
    bg: 'linear-gradient(135deg, #854d0e, #a16207)',
    border: '#fde047',
    badge: '#eab308',
    icon: CloudLightning,
    label: 'YELLOW ALERT · BE AWARE & MONITOR',
  },
  GREEN: {
    bg: 'linear-gradient(135deg, #14532d, #166534)',
    border: '#86efac',
    badge: '#22c55e',
    icon: Waves,
    label: 'GREEN · NORMAL WEATHER CONDITIONS',
  },
};

export default function EarlyWarningBanner({ alertLevel = 'ORANGE', primaryHazard = 'THUNDERSTORM & RAINFALL', leadTimeMinutes = 30, advisory, zoneName = 'Kolkata Metropolitan Area' }) {
  const theme = alertThemes[alertLevel] || alertThemes.YELLOW;
  const Icon = theme.icon;

  return (
    <div
      style={{
        background: theme.bg,
        border: `1px solid ${theme.border}`,
        borderRadius: 12,
        padding: '16px 20px',
        color: '#ffffff',
        marginBottom: 16,
        boxShadow: '0 8px 24px rgba(0,0,0,0.15)',
        display: 'flex',
        flexDirection: 'column',
        gap: 8,
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 10 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{ background: 'rgba(255,255,255,0.2)', padding: 8, borderRadius: 8, display: 'grid', placeItems: 'center' }}>
            <Icon size={22} color="#ffffff" />
          </div>
          <div>
            <span style={{ fontSize: 11, fontWeight: 800, letterSpacing: 1.2, opacity: 0.9 }}>
              {theme.label}
            </span>
            <h3 style={{ margin: 0, fontSize: 18, fontWeight: 700, letterSpacing: -0.3 }}>
              {primaryHazard} — {zoneName}
            </h3>
          </div>
        </div>

        {leadTimeMinutes > 0 && (
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              background: 'rgba(0,0,0,0.3)',
              padding: '6px 12px',
              borderRadius: 20,
              fontSize: 13,
              fontWeight: 700,
              border: '1px solid rgba(255,255,255,0.25)',
            }}
          >
            <Clock size={15} />
            <span>Estimated Lead Time: <b>{leadTimeMinutes} mins</b></span>
          </div>
        )}
      </div>

      {advisory && (
        <p style={{ margin: '4px 0 0', fontSize: 13, opacity: 0.95, lineHeight: 1.4, background: 'rgba(0,0,0,0.15)', padding: '8px 12px', borderRadius: 6 }}>
          <b>Action Advisory:</b> {advisory}
        </p>
      )}
    </div>
  );
}
