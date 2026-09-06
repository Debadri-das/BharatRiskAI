import SimulationPanel from '../components/simulation/SimulationPanel';
import RecommendationPanel from '../components/recommendation/RecommendationPanel';
import { useRiskStore } from '../store/riskStore';
export default function Simulation() { const { selectedZone, simulated } = useRiskStore(); const recs = simulated?.zones?.[0]?.recommended_actions; return <div style={{ display: 'grid', gridTemplateColumns: '420px 1fr', gap: 16 }}><SimulationPanel zone={selectedZone()} /><RecommendationPanel recommendations={recs || []} /></div>; }
