package com.bharatrisk.mesh

import java.time.Instant
import kotlin.concurrent.thread

class MessageRouter(
    private val store: MessageStore,
    private val gateway: GatewayManager,
    private val transport: SimulatedTransport,
    private val node: MeshNode
) : MeshNode {

    override fun onReceive(payload: String, from: MeshNode) {
        try {
            val pkt = MeshPacket.fromJson(payload)
            println("[Router] Received ${pkt.message_id} at node (hop=${pkt.hop_count}, ttl=${pkt.ttl})")
            // duplicate detection
            if (store.hasSeen(pkt.message_id)) { println("[Router] Duplicate ${pkt.message_id}, ignoring"); return }

            // timestamp validation (reject very old packets)
            val created = Instant.parse(pkt.created_at)
            if (Instant.now().minusSeconds(60 * 60 * 24).isAfter(created)) { println("[Router] Stale ${pkt.message_id}"); return }

            // signature check (demo)
            val sigOk = pkt.signature?.let { EncryptionManager.verify(payloadWithoutSig(payload), it) } ?: false
            if (!sigOk) { println("[Router] Invalid signature for ${pkt.message_id}"); return }

            // TTL
            if (pkt.ttl <= 0) { println("[Router] TTL expired for ${pkt.message_id}"); return }

            // store locally
            store.store(pkt)
            println("[Router] Stored ${pkt.message_id} locally")

            // If we have internet, push to gateway asynchronously
            thread {
                if (gateway.hasConnectivity()) {
                    try {
                        println("[Router] Gateway available, forwarding ${pkt.message_id}")
                        gateway.forward(pkt)
                        store.remove(pkt.message_id)
                        println("[Router] Gateway accepted ${pkt.message_id}, removed from store")
                    } catch (ex: Exception) {
                        println("[Router] Gateway forward failed for ${pkt.message_id}: ${ex.message}")
                    }
                }
            }

            // forward to neighbors with decremented TTL
            pkt.hop_count += 1
            pkt.ttl -= 1
            val out = pkt.toJson()
            println("[Router] Forwarding ${pkt.message_id} to neighbors (hop=${pkt.hop_count}, ttl=${pkt.ttl})")
            transport.broadcast(node, out)

        } catch (ex: Exception) {
            println("[Router] Error processing payload: ${ex.message}")
        }
    }

    fun originateAndSend(pkt: MeshPacket) {
        // sign
        val payload = pkt.toJson()
        pkt.signature = EncryptionManager.sign(payload)
        println("[Router] Originating ${pkt.message_id} (signed)")
        store.store(pkt)
        println("[Router] Stored originated ${pkt.message_id}")
        // attempt gateway then broadcast
        thread {
            if (gateway.hasConnectivity()) {
                try {
                    println("[Router] Gateway available, sending originated ${pkt.message_id}")
                    gateway.forward(pkt)
                    store.remove(pkt.message_id)
                    println("[Router] Gateway accepted originated ${pkt.message_id}")
                } catch (ex: Exception) { println("[Router] Gateway forward failed: ${ex.message}") }
            }
            transport.broadcast(node, pkt.toJson())
        }
    }

    private fun payloadWithoutSig(payload: String): String {
        // remove signature field for verification expectation (we sign the JSON without signature)
        return try {
            val o = org.json.JSONObject(payload)
            o.remove("signature")
            o.toString()
        } catch (ex: Exception) { payload }
    }
}
package com.bharatrisk.mesh

import java.time.Duration
import java.time.Instant

class MessageRouter(private val store: MessageStore, private val encryption: EncryptionManager) {
    fun receive(packet: MeshPacket): RouteResult {
        if (store.hasSeen(packet.messageId)) return RouteResult("duplicate", null)
        if (packet.ttl <= 0) return RouteResult("expired", null)
        if (Duration.between(Instant.parse(packet.createdAt), Instant.now()).toHours() > 24) return RouteResult("stale", null)
        if (!encryption.verify(packet)) return RouteResult("invalid_signature", null)
        store.save(packet)
        return RouteResult("forward", packet.forwarded())
    }
}

data class RouteResult(val status: String, val packetToForward: MeshPacket?)
