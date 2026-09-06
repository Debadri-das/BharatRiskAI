import CitizenReportForm from '../components/reports/CitizenReportForm';
import ReportList from '../components/reports/ReportList';
import { useRiskStore } from '../store/riskStore';
export default function Reports() { const dashboard = useRiskStore((s) => s.dashboard); return <div style={{ display: 'grid', gridTemplateColumns: '420px 1fr', gap: 16 }}><CitizenReportForm /><ReportList reports={dashboard.reports} /></div>; }
