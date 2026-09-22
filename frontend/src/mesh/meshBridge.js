import { createPacket, forwardPacket } from './packet';

const SIGNALING_VERSION = 1;

export function createMeshNodeId() {
  const key = 'bharatrisk-mesh-node-id';
  let id = localStorage.getItem(key);
  if (!id) {
    const randomPart = typeof crypto?.randomUUID === 'function'
      ? crypto.randomUUID()
      : typeof crypto?.getRandomValues === 'function'
        ? Array.from(crypto.getRandomValues(new Uint8Array(8)), (value) => value.toString(16).padStart(2, '0')).join('')
        : `${Date.now().toString(16)}-${Math.random().toString(16).slice(2)}`;
    id = `NODE-${randomPart.slice(0, 8).toUpperCase()}`;
    localStorage.setItem(key, id);
  }
  return id;
}

export function createMeshPeer({ initiator, onMessage, onStateChange }) {
  const connection = new RTCPeerConnection({ iceServers: [] });
  let channel = initiator ? connection.createDataChannel('bharatrisk-mesh') : null;
  const notify = (state) => onStateChange?.(state);

  const attachChannel = (nextChannel) => {
    channel = nextChannel;
    channel.onopen = () => notify('CONNECTED');
    channel.onclose = () => notify('DISCONNECTED');
    channel.onerror = () => notify('ERROR');
    channel.onmessage = (event) => {
      try {
        onMessage?.(JSON.parse(event.data));
      } catch {
        notify('INVALID_MESSAGE');
      }
    };
  };

  if (channel) attachChannel(channel);
  connection.ondatachannel = (event) => attachChannel(event.channel);
  connection.onconnectionstatechange = () => notify(connection.connectionState.toUpperCase());
  connection.onicecandidate = () => {};

  const waitForIce = () => new Promise((resolve) => {
    if (connection.iceGatheringState === 'complete') {
      resolve();
      return;
    }
    const check = () => {
      if (connection.iceGatheringState === 'complete') {
        connection.removeEventListener('icegatheringstatechange', check);
        resolve();
      }
    };
    connection.addEventListener('icegatheringstatechange', check);
    window.setTimeout(() => {
      connection.removeEventListener('icegatheringstatechange', check);
      resolve();
    }, 5000);
  });

  return {
    async createOffer() {
      const offer = await connection.createOffer();
      await connection.setLocalDescription(offer);
      await waitForIce();
      return JSON.stringify({ version: SIGNALING_VERSION, description: connection.localDescription });
    },
    async acceptOffer(signal) {
      const parsed = JSON.parse(signal);
      if (parsed.version !== SIGNALING_VERSION) throw new Error('Unsupported mesh pairing code.');
      await connection.setRemoteDescription(parsed.description);
      const answer = await connection.createAnswer();
      await connection.setLocalDescription(answer);
      await waitForIce();
      return JSON.stringify({ version: SIGNALING_VERSION, description: connection.localDescription });
    },
    async acceptAnswer(signal) {
      const parsed = JSON.parse(signal);
      if (parsed.version !== SIGNALING_VERSION) throw new Error('Unsupported mesh pairing code.');
      await connection.setRemoteDescription(parsed.description);
    },
    send(message) {
      if (channel?.readyState !== 'open') throw new Error('Mesh link is not connected.');
      channel.send(JSON.stringify(message));
    },
    close() {
      channel?.close();
      connection.close();
    },
  };
}

export function createMeshSosPacket(payload, nodeId = createMeshNodeId()) {
  return createPacket({ ...payload, source_node: nodeId, ttl: 10 });
}

export function relayMeshPacket(packet, nodeId) {
  return forwardPacket({ ...packet, relay_node: nodeId }, nodeId);
}
