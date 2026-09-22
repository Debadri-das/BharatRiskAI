import React, { useEffect } from 'react';
import Sidebar from './components/layout/Sidebar';
import Header from './components/layout/Header';
import OfflineBanner from './components/common/OfflineBanner';
import ErrorBoundary from './components/common/ErrorBoundary';
import Dashboard from './pages/Dashboard';
import RiskAnalysis from './pages/RiskAnalysis';
import Reports from './pages/Reports';
import EmergencyCenter from './pages/EmergencyCenter';
import Settings from './pages/Settings';
import MeshSimulator from './pages/MeshSimulator';
import ProjectDetails from './pages/ProjectDetails';
import { useRiskStore } from './store/riskStore';
import { useUiStore } from './store/uiStore';
import { usePreferencesStore } from './store/preferencesStore';
import { useNotificationStore } from './store/notificationStore';
import { getNowcastAlerts } from './services/nowcastApi';

const pages = { Dashboard, 'Risk Analysis': RiskAnalysis, Reports, 'Emergency Center': EmergencyCenter, 'Mesh Simulator': MeshSimulator, Settings, 'Project Details': ProjectDetails };

export default function App() {
  const load = useRiskStore((s) => s.load);
  const page = useUiStore((s) => s.page);
  const darkMode = usePreferencesStore((s) => s.darkMode);
  const addThreatNotifications = useNotificationStore((s) => s.addThreatNotifications);

  useEffect(() => {
    document.documentElement.classList.toggle('dark-mode', darkMode);
  }, [darkMode]);

  useEffect(() => {
    load();
    const refreshTimer = window.setInterval(load, 30000);
    return () => window.clearInterval(refreshTimer);
  }, [load]);

  useEffect(() => {
    let cancelled = false;
    const checkThreats = async () => {
      try {
        const data = await getNowcastAlerts(false);
        if (!cancelled) addThreatNotifications(data.alerts);
      } catch {
        // The dashboard remains usable when the prediction feed is temporarily unavailable.
      }
    };
    checkThreats();
    const timer = window.setInterval(checkThreats, 30000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [addThreatNotifications]);

  const Page = pages[page] || Dashboard;

  return (
    <ErrorBoundary>
      <div className="app-shell">
        <Sidebar />
        <main className="main-content">
          <Header />
          <OfflineBanner />
          <Page />
        </main>
      </div>
    </ErrorBoundary>
  );
}
