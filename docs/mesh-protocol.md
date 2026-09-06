# Mesh Protocol

SOS packets include a message ID, type, emergency type, GPS location, people count, vulnerable groups, priority, timestamp, TTL, hop count, and signature.

Routing flow:

1. Receive packet.
2. Validate schema.
3. Reject duplicate message IDs.
4. Reject stale timestamps.
5. Verify signature.
6. Stop if TTL expired.
7. Store locally.
8. Increment hop count and decrement TTL.
9. Forward to nearby peer or gateway.

This prevents indefinite forwarding. The browser dashboard does not claim arbitrary Bluetooth mesh support; Android handles nearby-device communication or runs the simulator for demos.
