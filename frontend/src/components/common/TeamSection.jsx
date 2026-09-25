import React, { useState } from 'react';
import { Users, Award, Shield } from 'lucide-react';

export const TEAM_MEMBERS = [
  {
    name: 'Debadri Das',
    role: 'Fullstack & Geospatial AI',
    image: '/team/debadri.jpg',
    initials: 'DD',
    bg: 'linear-gradient(135deg, #2563eb, #1d4ed8)',
  },
  {
    name: 'Anuj Dutta',
    role: 'ML & Satellite Pipeline Lead',
    image: '/team/anuj.jpg',
    initials: 'AD',
    bg: 'linear-gradient(135deg, #059669, #047857)',
  },
  {
    name: 'Anu Kumari Singh',
    role: 'Data Engineering & Analysis',
    image: '/team/anu.jpg',
    initials: 'AS',
    bg: 'linear-gradient(135deg, #7c3aed, #6d28d9)',
  },
  {
    name: 'Sharanya Bagchi',
    role: 'Frontend & UI/UX Design',
    image: '/team/sharanya.jpg',
    initials: 'SB',
    bg: 'linear-gradient(135deg, #db2777, #be185d)',
  },
  {
    name: 'Priya Maity',
    role: 'Quality Assurance & Testing',
    image: '/team/priya.jpg',
    initials: 'PM',
    bg: 'linear-gradient(135deg, #d97706, #b45309)',
  },
  {
    name: 'Rituraj Pandey',
    role: 'Research & Model Evaluation',
    image: '/team/rituraj.jpg',
    initials: 'RP',
    bg: 'linear-gradient(135deg, #0891b2, #0e7490)',
  },
];

function TeamMemberCard({ member }) {
  const [imgError, setImgError] = useState(false);

  return (
    <article
      className="panel"
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        padding: '20px 14px',
        textAlign: 'center',
        borderRadius: 12,
        transition: 'transform 0.2s ease, box-shadow 0.2s ease',
        background: 'var(--panel-bg, #ffffff)',
      }}
    >
      <div
        style={{
          width: 90,
          height: 90,
          borderRadius: '50%',
          overflow: 'hidden',
          marginBottom: 12,
          boxShadow: '0 4px 12px rgba(0,0,0,0.12)',
          border: '3px solid #ffffff',
          display: 'grid',
          placeItems: 'center',
          background: member.bg,
          color: '#ffffff',
          fontWeight: 700,
          fontSize: 24,
          letterSpacing: '0.05em',
          position: 'relative',
        }}
      >
        {!imgError ? (
          <img
            src={member.image}
            alt={member.name}
            onError={() => setImgError(true)}
            style={{
              width: '100%',
              height: '100%',
              objectFit: 'cover',
            }}
          />
        ) : (
          <span>{member.initials}</span>
        )}
      </div>

      <h3 style={{ margin: '0 0 4px', fontSize: 15, fontWeight: 700, color: 'var(--ink, #14211d)' }}>
        {member.name}
      </h3>
      <p style={{ margin: '0 0 8px', fontSize: 12, color: 'var(--muted, #657871)', fontWeight: 500 }}>
        {member.role}
      </p>
      <span
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: 4,
          fontSize: 10,
          fontWeight: 700,
          padding: '2px 8px',
          borderRadius: 12,
          background: 'rgba(37, 99, 235, 0.08)',
          color: '#2563eb',
          textTransform: 'uppercase',
          letterSpacing: '0.04em',
        }}
      >
        <Shield size={10} /> CaffineCoders
      </span>
    </article>
  );
}

export default function TeamSection() {
  return (
    <section className="team-section-container" style={{ marginTop: 32, marginBottom: 24 }}>
      <div className="panel-heading" style={{ marginBottom: 16 }}>
        <div>
          <span className="section-kicker" style={{ display: 'inline-flex', alignItems: 'center', gap: 5 }}>
            <Award size={13} /> SMART INDIA HACKATHON 2026
          </span>
          <h2 style={{ margin: '4px 0 2px' }}>Meet Team CaffineCoders</h2>
          <p style={{ margin: 0, fontSize: 13, color: 'var(--muted, #657871)' }}>
            The creators and engineers behind BharatRisk AI
          </p>
        </div>
      </div>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))',
          gap: 14,
        }}
      >
        {TEAM_MEMBERS.map((member) => (
          <TeamMemberCard key={member.name} member={member} />
        ))}
      </div>
    </section>
  );
}
