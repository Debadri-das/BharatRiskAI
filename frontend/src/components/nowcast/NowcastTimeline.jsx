import React, { useState } from 'react';
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, BarChart, Bar, Legend } from 'recharts';
import { CloudRain, Radio, Zap, Wind, ShieldAlert } from 'lucide-react';

export default function NowcastTimeline({ timeline = [], zoneName = 'Zone' }) {
  const [selectedIndex, setSelectedIndex] = useState(1); // default to +30m

  if (!timeline || timeline.length === 0) {
    return (
      <div className="panel" style={{ padding: 16 }}>
        <p style={{ margin: 0, color: '#657871' }}>Generating 0-6h nowcast trajectory...</p>
      </div>
    );
  }

  const activeStep = timeline[selectedIndex] || timeline[0];

  return (
    <section className="panel" style={{ padding: 18, marginBottom: 14 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <div>
          <span className="section-kicker" style={{ color: '#0f766e', fontSize: 10, fontWeight: 800 }}>AI WEATHER NOWCASTING (0-6H)</span>
          <h2 style={{ margin: '2px 0 0', fontSize: 17, fontWeight: 700 }}>Convective Trajectory & Rainfall Intensity</h2>
        </div>
        <span style={{ fontSize: 12, fontWeight: 700, color: '#0f766e', background: '#d9f2e8', padding: '4px 10px', borderRadius: 12 }}>
          {zoneName}
        </span>
      </div>

      {/* Trajectory Area Chart */}
      <div style={{ height: 160, width: '100%', marginBottom: 12 }}>
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={timeline} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
            <defs>
              <linearGradient id="rainGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#0f766e" stopOpacity={0.8} />
                <stop offset="95%" stopColor="#0f766e" stopOpacity={0.05} />
              </linearGradient>
              <linearGradient id="dbzGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#d97706" stopOpacity={0.6} />
                <stop offset="95%" stopColor="#d97706" stopOpacity={0.0} />
              </linearGradient>
            </defs>
            <XAxis dataKey="interval" tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} />
            <Tooltip
              contentStyle={{ background: '#14211d', color: '#ffffff', borderRadius: 8, fontSize: 12, border: 0 }}
              formatter={(value, name) => [
                name === 'rain_rate_mm_hr' ? `${value} mm/h` : name === 'radar_dbz' ? `${value} dBZ` : `${value}%`,
                name === 'rain_rate_mm_hr' ? 'Rainfall Rate' : name === 'radar_dbz' ? 'Radar Reflectivity' : 'Thunderstorm Prob',
              ]}
            />
            <Area type="monotone" dataKey="rain_rate_mm_hr" stroke="#0f766e" strokeWidth={2.5} fillOpacity={1} fill="url(#rainGradient)" name="rain_rate_mm_hr" />
            <Area type="monotone" dataKey="radar_dbz" stroke="#d97706" strokeWidth={1.5} strokeDasharray="3 3" fillOpacity={1} fill="url(#dbzGradient)" name="radar_dbz" />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {/* Interval Selector Tabs */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 6, marginBottom: 14 }}>
        {timeline.map((step, idx) => (
          <button
            key={step.interval}
            onClick={() => setSelectedIndex(idx)}
            className="btn"
            style={{
              padding: '6px 4px',
              fontSize: 11,
              fontWeight: 700,
              background: selectedIndex === idx ? '#0f766e' : '#f0f4f2',
              color: selectedIndex === idx ? '#ffffff' : '#334e45',
              border: '1px solid',
              borderColor: selectedIndex === idx ? '#0f766e' : '#cbd8d2',
              borderRadius: 6,
            }}
          >
            +{step.interval}
          </button>
        ))}
      </div>

      {/* Step Highlights */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10, background: '#f8faf9', padding: 12, borderRadius: 8 }}>
        <div>
          <span style={{ fontSize: 10, color: '#657871', fontWeight: 700, display: 'flex', alignItems: 'center', gap: 4 }}>
            <CloudRain size={12} color="#0f766e" /> RAIN RATE
          </span>
          <strong style={{ fontSize: 16, color: '#14211d' }}>{activeStep.rain_rate_mm_hr} <small style={{ fontSize: 10 }}>mm/h</small></strong>
        </div>
        <div>
          <span style={{ fontSize: 10, color: '#657871', fontWeight: 700, display: 'flex', alignItems: 'center', gap: 4 }}>
            <Radio size={12} color="#d97706" /> RADAR PROXY
          </span>
          <strong style={{ fontSize: 16, color: '#14211d' }}>{activeStep.radar_dbz} <small style={{ fontSize: 10 }}>dBZ</small></strong>
        </div>
        <div>
          <span style={{ fontSize: 10, color: '#657871', fontWeight: 700, display: 'flex', alignItems: 'center', gap: 4 }}>
            <Zap size={12} color="#9333ea" /> THUNDERSTORM
          </span>
          <strong style={{ fontSize: 16, color: '#14211d' }}>{activeStep.thunderstorm_prob}%</strong>
        </div>
        <div>
          <span style={{ fontSize: 10, color: '#657871', fontWeight: 700, display: 'flex', alignItems: 'center', gap: 4 }}>
            <ShieldAlert size={12} color="#b91c1c" /> INUNDATION
          </span>
          <strong style={{ fontSize: 16, color: '#14211d' }}>{activeStep.flood_threat_score}<small style={{ fontSize: 10 }}>/100</small></strong>
        </div>
      </div>
    </section>
  );
}
