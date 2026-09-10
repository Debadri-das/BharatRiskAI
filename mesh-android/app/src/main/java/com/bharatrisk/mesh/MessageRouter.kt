package com.bharatrisk.mesh

import java.time.Instant

data class RouteResult(val status: String, val packetToForward: MeshPacket?)

class MessageRouter(
    private val store: MessageStore = MessageStore(),
    private val gateway: GatewayManager = GatewayManager()
) {
    fun receive(packet: MeshPacket): RouteResult {
        if (store.hasSeen(packet.message_id)) {
            return RouteResult("DUPLICATE", null)
        }
        if (packet.ttl <= 0) {
            return RouteResult("EXPIRED", null)
        }

        store.store(packet)

        if (gateway.hasConnectivity()) {
            val sent = gateway.forward(packet)
            if (sent) {
                store.remove(packet.message_id)
                return RouteResult("DELIVERED_TO_GATEWAY", null)
            }
        }

        val nextPacket = packet.forwarded("CURRENT_NODE")
        return RouteResult("FORWARDING", nextPacket)
    }
}
