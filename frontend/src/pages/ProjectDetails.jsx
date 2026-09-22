import { Activity, Bell, BrainCircuit, CloudRain, Database, GitBranch, Globe2, Layers3, Map, Radio, ShieldCheck, Users, WifiOff } from 'lucide-react';

const team = [
  'Anu Kumari Singh',
  'Anuj Dutta',
  'Debadri das',
  'Sharanya Bagchi',
  'Priya Maity',
  'Rituraj pandey',
];

const sections = [
  {
    icon: ShieldCheck,
    title: 'The problem we solve',
    text: 'BharatRisk AI is designed for rapidly intensifying, localized events such as severe thunderstorms, cloudbursts, and flash floods. It turns complex atmospheric signals into an actionable 2–6 hour warning window for communities and disaster-response teams.',
  },
  {
    icon: BrainCircuit,
    title: 'AI nowcasting engine',
    text: 'A multi-task spatiotemporal model shares a feature backbone across three hazard heads. It evaluates moisture, instability, lift, wind structure, cloud-top cooling, precipitation, and terrain to produce separate probability and risk outputs for thunderstorms, cloudbursts, and flash floods.',
  },
  {
    icon: Database,
    title: 'Data fusion',
    text: 'The ingestion layer aligns atmospheric reanalysis, satellite observations, quantitative precipitation estimates, and elevation rasters on a common spatial and temporal grid. Provider adapters validate required variables and record ingestion runs instead of silently inventing missing observations.',
  },
  {
    icon: CloudRain,
    title: 'Real atmospheric signals',
    text: 'Integrated water vapor is derived by vertically integrating specific humidity through pressure levels. Cloud-top temperature is derived from calibrated thermal-infrared brightness temperature, while temporal change rates highlight rapid moisture accumulation and explosive updraft development.',
  },
  {
    icon: Map,
    title: 'Terrain-aware flood risk',
    text: 'DEM elevation and slope are combined with rainfall and drainage characteristics to estimate where intense precipitation is most likely to collect or move. The map presents these localized risks as operational zones rather than only regional weather summaries.',
  },
  {
    icon: Bell,
    title: 'Warnings and notifications',
    text: 'The dashboard polls the live prediction feed, deduplicates yellow, orange, and red threats, and presents them in the notification center. Browser notifications can be enabled from Settings, while backend delivery adapters support responder webhooks and SMS gateways.',
  },
  {
    icon: WifiOff,
    title: 'Offline resilience',
    text: 'SOS requests are stored in the response queue and can be routed by email to the configured response address. Delivery status is returned with each request so operators can act on failures.',
  },
  {
    icon: Activity,
    title: 'Operational workflow',
    text: 'Data is ingested, normalized, persisted, and passed to inference. Risk maps and explainable triggers are shown to operators, citizens can submit reports or SOS messages, alerts are delivered when thresholds are crossed, and all important actions remain visible in dedicated sections.',
  },
];

export default function ProjectDetails() {
  return (
    <div className="project-details-page">
      <section className="project-details-hero">
        <div>
          <span className="section-kicker"><Globe2 size={14} /> PROJECT OVERVIEW</span>
          <h1>Warnings that reach people before the storm does.</h1>
          <p>BharatRisk AI is a hyper-local severe-weather intelligence and emergency-response platform for earlier decisions, clearer warnings, and resilient communication.</p>
        </div>
        <div className="project-hero-mark"><Radio size={30} /><span>2–6h<br />lead time</span></div>
      </section>

      <section className="project-section">
        <div className="project-section-heading"><span className="section-kicker"><Layers3 size={14} /> HOW THE PLATFORM WORKS</span><h2>From raw signals to an actionable warning</h2><p>Every layer is designed to reduce latency while keeping the reason for a warning understandable.</p></div>
        <div className="project-overview-grid">
          {sections.map(({ icon: Icon, title, text }) => <article className="project-detail-card panel" key={title}><span className="project-detail-icon"><Icon size={19} /></span><h3>{title}</h3><p>{text}</p></article>)}
        </div>
      </section>

      <section className="project-architecture panel">
        <div className="project-section-heading"><span className="section-kicker"><GitBranch size={14} /> END-TO-END PIPELINE</span><h2>One connected response loop</h2></div>
        <div className="project-pipeline">{['MOSDAC products', 'INSAT-3D signals', 'IMDAA atmosphere', 'ML inference', 'Risk map + XAI', 'Alerts + SOS'].map((item, index) => <div className="project-pipeline-step" key={item}><span>{String(index + 1).padStart(2, '0')}</span><strong>{item}</strong>{index < 5 && <b>→</b>}</div>)}</div>
      </section>

      <section className="project-section">
        <div className="project-section-heading"><span className="section-kicker"><Users size={14} /> TEAM</span><h2>CaffineCoders</h2><p>The team building a practical early-warning experience for India’s local disaster-response needs.</p></div>
        <div className="team-grid">{team.map((member) => <article className="team-card panel" key={member}><div className="team-image-placeholder"><Users size={24} /><span>Add image</span></div><h3>{member}</h3><p>CaffineCoders</p></article>)}</div>
      </section>

      <section className="project-note panel"><span className="project-detail-icon"><CloudRain size={19} /></span><div><h3>Operational status</h3><p>The dashboard consumes decoded INSAT-3D and IMDAA products refreshed by the worker. Provider credentials and product download endpoints remain deployment configuration, and the API reports readiness when both products are current.</p></div></section>
    </div>
  );
}
