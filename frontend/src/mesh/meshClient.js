import { createPacket, forwardPacket } from './packet';
import { signPacket } from './crypto';

export async function simulateMeshRoute(payload) {
  let packet = createPacket(payload);
  packet.signature = await signPacket(packet);
  return ['PHONE A', 'PHONE B', 'PHONE C', 'GATEWAY'].map((node) => {
    packet = forwardPacket(packet, node);
    return { node, packet: { ...packet }, status: packet.dropped ? 'DROPPED' : 'FORWARDED' };
  });
}
