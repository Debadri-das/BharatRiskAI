import { useEffect, useRef, useState } from 'react';
import { CheckCircle2, Clipboard, Copy, Link2, Radio, Router, Send, ShieldAlert, Wifi, WifiOff } from 'lucide-react';
import { getCitywideNowcast } from '../services/nowcastApi';
import { sendEmergency } from '../services/emergencyApi';
import { createMeshNodeId, createMeshPeer, createMeshSosPacket, relayMeshPacket } from '../mesh/meshBridge';

function copyText(value) {
  if (!value) return Promise.resolve();
  return navigator.clipboard?.writeText(value);
}

export default function MeshSimulator() {
  const [role, setRole] = useState('gateway');
  const [nodeId] = useState(createMeshNodeId);
  const [signal, setSignal] = useState('');
  const [response, setResponse] = useState('');
  const [status, setStatus] = useState('DISCONNECTED');
  const [message, setMessage] = useState('Choose Gateway on the connected device and Peer on an offline device.');
  const [received, setReceived] = useState([]);
  const peersRef = useRef(new Map());
  const pendingRef = useRef(null);

  useEffect(() => () => {
    pendingRef.current?.close();
    peersRef.current.forEach((peer) => peer.close());
  }, []);

  useEffect(() => {
    if (role !== 'gateway') return undefined;
    const broadcast = async () => {
      if (!peersRef.current.size) return;
      try {
        const nowcast = await getCitywideNowcast(false);
        peersRef.current.forEach((peer) => peer.send({ type: 'NOWCAST_UPDATE', source: nodeId, sentAt: new Date().toISOString(), payload: nowcast }));
        setMessage('Live nowcast snapshot broadcast to paired peers.');
      } catch {
        setMessage('The gateway could not retrieve the current risk feed.');
      }
    };
    broadcast();
    const timer = window.setInterval(broadcast, 30000);
    return () => window.clearInterval(timer);
  }, [role, nodeId]);

  async function createPairingOffer() {
    pendingRef.current?.close();
    pendingRef.current = createMeshPeer({ initiator: true, onMessage: handleMessage, onStateChange: setStatus });
    setSignal(await pendingRef.current.createOffer());
    setMessage('Copy this offer to the offline peer. Paste its answer below after it responds.');
  }

  async function acceptPairingOffer() {
    pendingRef.current?.close();
    pendingRef.current = createMeshPeer({ initiator: false, onMessage: handleMessage, onStateChange: setStatus });
    setResponse(await pendingRef.current.acceptOffer(signal));
    peersRef.current.set('GATEWAY', pendingRef.current);
    pendingRef.current = null;
    setMessage('Copy this answer back to the gateway, then wait for CONNECTED.');
  }

  async function acceptPairingAnswer() {
    await pendingRef.current?.acceptAnswer(response);
    if (pendingRef.current) peersRef.current.set(`PEER-${peersRef.current.size + 1}`, pendingRef.current);
    pendingRef.current = null;
    setMessage('Pairing completed. Waiting for the direct local link.');
  }

  function handleMessage(packet) {
    setReceived((items) => [{ ...packet, receivedAt: new Date().toISOString() }, ...items].slice(0, 10));
    if (role === 'gateway' && packet.type === 'EMERGENCY') {
      sendEmergency(packet).then(() => setMessage('Offline peer SOS delivered to the connected response API.')).catch(() => setMessage('Peer SOS received, but the response API could not be reached.'));
      return;
    }
    setMessage(packet.type === 'NOWCAST_UPDATE' ? 'Live nowcast snapshot received from the gateway.' : 'Mesh packet received.');
  }

  async function sendSos() {
    try {
      const packet = relayMeshPacket(createMeshSosPacket({
        emergency_type: 'TRAPPED',
        latitude: 22.546,
        longitude: 88.438,
        people: 4,
        priority: 'CRITICAL',
      }, nodeId), nodeId);
      peersRef.current.forEach((peer) => peer.send(packet));
      setMessage('SOS sent through the direct mesh link.');
    } catch (error) {
      setMessage(error.message);
    }
  }

  async function broadcastNowcast() {
    try {
      const nowcast = await getCitywideNowcast(false);
      peersRef.current.forEach((peer) => peer.send({ type: 'NOWCAST_UPDATE', source: nodeId, sentAt: new Date().toISOString(), payload: nowcast }));
      setMessage('Current risk snapshot broadcast to the paired peer.');
    } catch {
      setMessage('The gateway could not retrieve the current risk feed.');
    }
  }

  return <div className="records-page mesh-simulator-page">
    <section className="page-intro">
      <div><span className="section-kicker">REAL WEBRTC MESH</span><h1>Nearby resilience network</h1><p>Pair devices over local Wi‑Fi, then exchange SOS packets and risk snapshots directly without mobile data.</p></div>
      <span className="simulator-badge"><Wifi size={14} /> Local peer transport</span>
    </section>
    <section className="mesh-hero panel">
      <div className="mesh-hero-copy"><span className="section-kicker">DIRECT DEVICE LINK</span><h2>One gateway keeps the group informed.</h2><p>WebRTC data channels work peer-to-peer over a nearby Wi‑Fi network. Signaling is copied between devices once; data then travels directly and is never routed through our server.</p>
        <div className="mesh-role-tabs">{['gateway', 'peer'].map((item) => <button className={`btn ${role === item ? '' : 'secondary'}`} onClick={() => setRole(item)} key={item}>{item === 'gateway' ? <Router size={15} /> : <WifiOff size={15} />}{item === 'gateway' ? 'Internet gateway' : 'Offline peer'}</button>)}</div>
      </div><div className="mesh-node-live"><Radio size={22} /><strong>{nodeId}</strong><span>{status}</span></div>
    </section>
    <section className="mesh-pairing panel">
      <div className="records-heading"><div><span className="section-kicker"><Link2 size={13} /> MANUAL PAIRING</span><h2>Connect this device</h2></div><span className={`record-count ${status === 'CONNECTED' ? 'connected' : ''}`}>{status}</span></div>
      {role === 'gateway' ? <div className="mesh-pair-grid"><div><button className="btn" onClick={createPairingOffer}><Link2 size={15} /> Create pairing offer</button><label className="field-label">Offer to copy<textarea readOnly value={signal} placeholder="Generate an offer, then copy it to the peer." /></label><button className="btn secondary" onClick={() => copyText(signal)} disabled={!signal}><Copy size={15} /> Copy offer</button></div><div><label className="field-label">Answer from peer<textarea value={response} onChange={(event) => setResponse(event.target.value)} placeholder="Paste the peer answer here." /></label><button className="btn" onClick={acceptPairingAnswer} disabled={!response}><CheckCircle2 size={15} /> Complete pairing</button></div></div>
        : <div className="mesh-pair-grid"><div><label className="field-label">Offer from gateway<textarea value={signal} onChange={(event) => setSignal(event.target.value)} placeholder="Paste the gateway offer here." /></label><button className="btn" onClick={acceptPairingOffer} disabled={!signal}><CheckCircle2 size={15} /> Create peer answer</button></div><div><label className="field-label">Answer to copy<textarea readOnly value={response} placeholder="Copy this answer back to the gateway." /></label><button className="btn secondary" onClick={() => copyText(response)} disabled={!response}><Copy size={15} /> Copy answer</button></div></div>}
      <p className="mesh-notice"><ShieldAlert size={15} />{message}</p>
    </section>
    <section className="mesh-actions panel"><div className="records-heading"><div><span className="section-kicker">LIVE MESH ACTIONS</span><h2>Exchange data</h2></div></div><div className="mesh-action-grid"><button className="btn warning" onClick={sendSos}><Send size={16} /> Send mesh SOS</button>{role === 'gateway' && <button className="btn secondary" onClick={broadcastNowcast}><Radio size={16} /> Broadcast nowcast</button>}</div></section>
    <section className="mesh-flow panel"><div className="records-heading"><div><span className="section-kicker">RECEIVED PACKETS</span><h2>Local device feed</h2></div><span className="record-count">{received.length} received</span></div>{received.length ? <div className="mesh-received-list">{received.map((item, index) => <article key={`${item.receivedAt}-${index}`}><strong>{item.type || 'MESH PACKET'}</strong><span>{item.source_node || item.source || 'unknown node'}</span><small>{new Date(item.receivedAt).toLocaleTimeString()}</small></article>)}</div> : <p className="notification-empty">No packets received on this device yet.</p>}</section>
  </div>;
}
