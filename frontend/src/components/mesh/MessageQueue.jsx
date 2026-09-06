import { useEffect, useState } from 'react';
import { queueSize } from '../../offline/offlineQueue';
export default function MessageQueue() { const [count, setCount] = useState(0); useEffect(() => { queueSize().then(setCount); }, []); return <section className="panel" style={{ padding: 16 }}><h3 style={{ marginTop: 0 }}>Offline Queue</h3><p>{count} pending local messages</p></section>; }
