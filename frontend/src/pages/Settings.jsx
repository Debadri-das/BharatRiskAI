import { useState } from 'react';
import { Bell, Database, MapPin, Moon, RefreshCw, ShieldCheck, Sun, UserRound, WifiOff } from 'lucide-react';
import { useEmergencyStore } from '../store/emergencyStore';
import { syncQueued } from '../offline/syncManager';
import { demoDashboard } from '../services/demoData';
import { useRiskStore } from '../store/riskStore';
import { usePreferencesStore } from '../store/preferencesStore';
import { useNotificationStore } from '../store/notificationStore';

export default function Settings() {
	const { offlineForced, setOfflineForced } = useEmergencyStore();
	const setDashboard = useRiskStore((s) => s.setDashboard);
	const { profile, darkMode, locationSharing, alertSounds, save } = usePreferencesStore();
	const [name, setName] = useState(profile.name);
	const [role, setRole] = useState(profile.role);
	const [saved, setSaved] = useState(false);
	const notificationPermission = useNotificationStore((state) => state.permission);
	const requestNotificationPermission = useNotificationStore((state) => state.requestPermission);

	function saveProfile(event) {
		event.preventDefault();
		save({ profile: { name: name.trim() || 'Field operator', role: role.trim() || 'Response coordinator' } });
		setSaved(true);
		window.setTimeout(() => setSaved(false), 2400);
	}

	return <div className="settings-page">
		<section className="page-intro"><div><span className="section-kicker">CONTROL ROOM PREFERENCES</span><h1>Settings</h1><p>Personalize your response workspace and data-sharing choices.</p></div><div className="settings-status"><ShieldCheck size={17} /> Preferences saved locally</div></section>
		<div className="settings-grid">
			<form className="settings-panel panel" onSubmit={saveProfile}>
				<div className="settings-heading"><span className="settings-icon"><UserRound size={18} /></span><div><h2>User account</h2><p>Shown on reports and response actions.</p></div></div>
				<label className="field-label">Display name<input value={name} onChange={(event) => setName(event.target.value)} /></label>
				<label className="field-label">Role<input value={role} onChange={(event) => setRole(event.target.value)} /></label>
				<button className="btn" type="submit"><UserRound size={15} /> Save profile</button>{saved && <span className="inline-success">Profile updated</span>}
			</form>
			<section className="settings-panel panel">
				<div className="settings-heading"><span className="settings-icon blue"><Moon size={18} /></span><div><h2>Appearance</h2><p>Keep the console comfortable during long shifts.</p></div></div>
				<button className="preference-row" onClick={() => save({ darkMode: !darkMode })}><span><strong>{darkMode ? <Moon size={16} /> : <Sun size={16} />} {darkMode ? 'Dark mode' : 'Light mode'}</strong><small>Switch the operations console theme</small></span><span className={`toggle ${darkMode ? 'on' : ''}`} /></button>
				<button className="preference-row" onClick={() => save({ alertSounds: !alertSounds })}><span><strong><Bell size={16} /> Alert sounds</strong><small>Allow audible critical-alert cues</small></span><span className={`toggle ${alertSounds ? 'on' : ''}`} /></button>
			</section>
			<section className="settings-panel panel">
				<div className="settings-heading"><span className="settings-icon green"><MapPin size={18} /></span><div><h2>Location sharing</h2><p>Control location access for nearby zones and reports.</p></div></div>
				<button className="preference-row" onClick={() => save({ locationSharing: !locationSharing })}><span><strong><MapPin size={16} /> Share device location</strong><small>{locationSharing ? 'Enabled for this browser' : 'Disabled until you enable it'}</small></span><span className={`toggle ${locationSharing ? 'on' : ''}`} /></button>
				<div className="privacy-note"><ShieldCheck size={15} /> Location is requested only when this option is enabled.</div>
			</section>
			<section className="settings-panel panel">
				<div className="settings-heading"><span className="settings-icon amber"><Bell size={18} /></span><div><h2>Threat notifications</h2><p>Receive browser alerts when a natural hazard is predicted.</p></div></div>
				<div className="notification-permission-row"><span><strong>{notificationPermission === 'granted' ? 'Browser notifications enabled' : 'Browser notifications disabled'}</strong><small>Alerts are deduplicated and only sent for yellow, orange, or red predictions.</small></span><button className="btn secondary" onClick={requestNotificationPermission}>{notificationPermission === 'granted' ? 'Enabled' : 'Enable alerts'}</button></div>
			</section>
			<section className="settings-panel panel">
				<div className="settings-heading"><span className="settings-icon amber"><Database size={18} /></span><div><h2>Data & connectivity</h2><p>Manage local demo data and queued field reports.</p></div></div>
				<div className="settings-actions"><button className="btn secondary" onClick={() => setOfflineForced(!offlineForced)}><WifiOff size={15} /> {offlineForced ? 'Restore connection' : 'Test offline mode'}</button><button className="btn secondary" onClick={() => syncQueued()}><RefreshCw size={15} /> Sync queued data</button><button className="btn warning" onClick={() => setDashboard(demoDashboard())}>Reset demo scenario</button></div>
				<p className="settings-footnote">Demo data is deterministic and remains available when the API is offline.</p>
			</section>
		</div>
	</div>;
}
