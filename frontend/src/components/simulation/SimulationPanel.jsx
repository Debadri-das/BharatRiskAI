import { useState } from 'react';
import { postSimulation } from '../../services/simulationApi';
import { score, recommendations } from '../../services/demoData';
import ParameterSlider from './ParameterSlider';
import SimulationResult from './SimulationResult';
import { useRiskStore } from '../../store/riskStore';

export default function SimulationPanel({ zone }) {
  const [rain, setRain] = useState(30), [drain, setDrain] = useState(-40), [duration, setDuration] = useState(24);
  const { setSimulated, simulated } = useRiskStore();
  async function run() {
    try { const res = await postSimulation({ rainfall_percentage: rain, drainage_efficiency_delta: drain, duration_hours: duration, zone_ids: [zone.id] }); setSimulated(res); }
    catch {
      const changed = { ...zone, rainfall_24h: zone.rainfall_24h * (1 + rain / 100), drainage_score: Math.max(0, zone.drainage_score + drain) };
      const simulated_risk = score(changed);
      setSimulated({ zones: [{ zone, original_risk: zone.risk_score, simulated_risk, difference: Math.round((simulated_risk - zone.risk_score) * 10) / 10, recommended_actions: recommendations(changed) }], newly_critical_zones: simulated_risk >= 76 && zone.risk_score < 76 ? [zone.id] : [], population_newly_affected: simulated_risk >= 76 && zone.risk_score < 76 ? zone.population : 0, affected_area_km2: zone.area_km2 });
    }
  }
  return <div style={{ display: 'grid', gap: 14 }}><section className="panel" style={{ padding: 16 }}><h3 style={{ marginTop: 0 }}>What-If Simulator</h3><ParameterSlider label="Rainfall" value={rain} min={-30} max={80} onChange={setRain} suffix="%" /><ParameterSlider label="Drainage efficiency" value={drain} min={-60} max={30} onChange={setDrain} suffix="%" /><ParameterSlider label="Duration" value={duration} min={1} max={72} onChange={setDuration} suffix="h" /><button className="btn" onClick={run}>Run Simulation</button></section><SimulationResult result={simulated} /></div>;
}
