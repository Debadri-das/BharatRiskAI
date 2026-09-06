export function createPacket(payload) {
  return { message_id: payload.message_id || `SOS-${Date.now()}`, type: 'EMERGENCY', ...payload, ttl: 10, hop_count: 0, created_at: new Date().toISOString() };
}

export function forwardPacket(packet, node) {
  if (packet.ttl <= 0) return { ...packet, dropped: true, node };
  return { ...packet, hop_count: packet.hop_count + 1, ttl: packet.ttl - 1, last_node: node };
}
