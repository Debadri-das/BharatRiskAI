Mesh Android Prototype
=====================

This folder contains a lightweight prototype of the mesh emergency protocol.

Design notes:
- `MeshPacket` — packet format with TTL, hop_count, and signature.
- `EncryptionManager` — HMAC-based signing for demonstration. In a real app use Android Keystore.
- `MessageStore` — simple file-based persistence for queued packets.
- `SimulatedTransport` — local broadcast simulator for multi-hop testing without hardware.
- `MessageRouter` — validates, deduplicates, stores, forwards and attempts gateway delivery.
- `GatewayManager` — sends POST `/api/emergency` when connectivity is available.
- `MeshManager` — high-level orchestrator for a device node.

Limitations:
- This is a protocol prototype and local simulator. Actual Bluetooth/Wi-Fi Direct logic must be implemented in Android platform APIs (BluetoothAdapter, WifiP2pManager, Nearby API, etc.).
- Keys are generated in memory for demo; for production move to Android Keystore and use asymmetric signatures.

How to test locally:
1. Build an Android app module and include these Kotlin files.
2. Use `SimulatedTransport` to register multiple `MeshManager` instances in tests and call `sendSOS()` to observe multi-hop forwarding and gateway delivery behavior.

Quick JVM harness:
1. To run a simple JVM test harness (no Android) compile and run `TestHarness.kt` with the Kotlin compiler or from an IDE.
2. The harness starts a local HTTP gateway on port `8001`, creates three in-memory nodes A→B→C sharing a `SimulatedTransport`, originates an SOS from A, and prints routing events and store contents.

Example (with Kotlin CLI):

```bash
kotlinc -cp "$(pwd)" -d mesh-android.jar mesh-android/app/src/main/java/com/bharatrisk/mesh/*.kt
kotlin -cp mesh-android.jar com.bharatrisk.mesh.TestHarnessKt
```

Note: You can also import the folder as a Kotlin/Java module in IntelliJ/Android Studio and run `TestHarness` directly.
