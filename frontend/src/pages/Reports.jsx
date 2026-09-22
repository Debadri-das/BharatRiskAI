import CitizenReportForm from '../components/reports/CitizenReportForm';
import ReportList from '../components/reports/ReportList';
import { useRiskStore } from '../store/riskStore';
export default function Reports() { const dashboard = useRiskStore((s) => s.dashboard); const load = useRiskStore((s) => s.load); return <div className="records-page"><section className="page-intro"><div><span className="section-kicker">CITIZEN INTELLIGENCE</span><h1>Field reports</h1><p>Review observations received from people on the ground.</p></div></section><div className="records-layout"><CitizenReportForm onSubmitted={() => load()} /><ReportList reports={dashboard.reports} /></div></div>; }
