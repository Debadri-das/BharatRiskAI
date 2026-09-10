package com.bharatrisk.mesh

class MeshManager(
    private val nodeId: String = "PHONE A",
    private val store: MessageStore = MessageStore(),
    private val gateway: GatewayManager = GatewayManager()
) {
    private val router = MessageRouter(store, gateway)

    fun sendSOS(packet: MeshPacket): RouteResult {
        return router.receive(packet)
    }

    fun simulateRoute(packet: MeshPacket = MeshPacket()): List<String> {
        val hops = listOf("PHONE A", "PHONE B", "PHONE C", "GATEWAY")
        val log = mutableListOf<String>()
        var currentPkt = packet

        for (hop in hops) {
            if (hop == "GATEWAY") {
                log.add("[$hop] Packet ${currentPkt.message_id} received. Uploaded to Emergency Command API (HTTP 200).")
            } else {
                log.add("[$hop] Relayed SOS ${currentPkt.message_id} (Hop: ${currentPkt.hop_count}, TTL: ${currentPkt.ttl})")
                currentPkt = currentPkt.forwarded(hop)
            }
        }
        return log
    }
}
