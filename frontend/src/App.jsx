import React, { useEffect } from 'react';
import Sidebar from './components/layout/Sidebar';
import Header from './components/layout/Header';
import BottomNav from './components/layout/BottomNav';
import OfflineBanner from './components/common/OfflineBanner';
import ErrorBoundary from './components/common/ErrorBoundary';
import Dashboard from './pages/Dashboard';
import RiskAnalysis from './pages/RiskAnalysis';
import Simulation from './pages/Simulation';
import Reports from './pages/Reports';
import EmergencyCenter from './pages/EmergencyCenter';
import Settings from './pages/Settings';
import { useRiskStore } from './store/riskStore';
import { useUiStore } from './store/uiStore';

const pages = { Dashboard, 'Risk Analysis': RiskAnalysis, Simulation, Reports, 'Emergency Center': EmergencyCenter, Settings };

export default function App() {
  const load = useRiskStore((s) => s.load);
  const page = useUiStore((s) => s.page);
  useEffect(() => { load(); }, [load]);
    useEffect(() => {
      load();
      const refreshTimer = window.setInterval(load, 30000);
      return () => window.clearInterval(refreshTimer);
    }, [load]);
  const Page = pages[page] || Dashboard;
  return (
    <ErrorBoundary>
      <div className="app-shell">
        <Sidebar />
        <main style={{ padding: 20, minWidth: 0 }}>
          <Header />
          <OfflineBanner />
          <Page />
        </main>
        <BottomNav />
      </div>
    </ErrorBoundary>
  );
}
