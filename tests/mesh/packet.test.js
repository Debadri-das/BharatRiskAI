import { describe, expect, it } from 'vitest';
import { createPacket, forwardPacket } from '../../frontend/src/mesh/packet';

describe('mesh packet', () => {
  it('decrements ttl and increments hop count', () => {
    const next = forwardPacket(createPacket({ emergency_type: 'TRAPPED', latitude: 1, longitude: 1, people: 4 }), 'PHONE B');
    expect(next.ttl).toBe(9);
    expect(next.hop_count).toBe(1);
  });
});
