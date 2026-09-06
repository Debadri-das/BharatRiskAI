import { useState } from 'react';
import EmergencyForm from '../components/mesh/EmergencyForm';
import MeshStatus from '../components/mesh/MeshStatus';
import MeshDevices from '../components/mesh/MeshDevices';
import MessageQueue from '../components/mesh/MessageQueue';
export default function EmergencyCenter() { const [route, setRoute] = useState([]); return <div style={{ display: 'grid', gridTemplateColumns: '360px 1fr', gap: 16 }}><EmergencyForm onRoute={setRoute} /><div style={{ display: 'grid', gap: 16 }}><MeshStatus route={route} /><MeshDevices /><MessageQueue /></div></div>; }
