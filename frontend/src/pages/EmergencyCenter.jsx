import EmergencyForm from '../components/emergency/EmergencyForm';
import EmergencyList from '../components/emergency/EmergencyList';
import { useState } from 'react';
export default function EmergencyCenter() { const [refreshKey, setRefreshKey] = useState(0); return <div className="records-page"><section className="page-intro"><div><span className="section-kicker">EMERGENCY OPERATIONS</span><h1>Emergency center</h1><p>Send help requests directly to the response database.</p></div></section><div className="emergency-layout"><EmergencyForm onSubmitted={() => setRefreshKey((key) => key + 1)} /><EmergencyList refreshKey={refreshKey} /></div></div>; }
