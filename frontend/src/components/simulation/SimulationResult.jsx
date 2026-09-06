import { number } from '../../utils/format';
export default function SimulationResult({ result }) {
  if (!result) return null;
  const top = result.zones?.[0];
  return <section className="panel" style={{ padding: 16 }}><h3 style={{ marginTop: 0 }}>Simulation Result</h3>{top && <p>Selected scenario moves top risk from <b>{top.original_risk}</b> to <b>{top.simulated_risk}</b>, a {top.difference >= 0 ? '+' : ''}{top.difference} shift.</p>}<p>Newly critical zones: <b>{result.newly_critical_zones?.length || 0}</b></p><p>Population newly affected: <b>{number(result.population_newly_affected)}</b></p><p>Affected area: <b>{result.affected_area_km2} km2</b></p></section>;
}
