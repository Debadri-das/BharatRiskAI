package com.bharatrisk.mesh

import java.util.concurrent.CopyOnWriteArrayList
import kotlin.concurrent.thread

/**
 * A simple simulated transport for testing multi-hop routing locally.
 * Devices register with the transport and can send messages to one another.
 */
class SimulatedTransport {
    private val devices = CopyOnWriteArrayList<MeshNode>()

    fun register(node: MeshNode) { devices.add(node) }

    fun unregister(node: MeshNode) { devices.remove(node) }

    fun broadcast(sender: MeshNode, payload: String) {
        // deliver asynchronously to all other devices
        for (d in devices) {
            if (d !== sender) {
                thread { d.onReceive(payload, sender) }
            }
        }
    }
}

interface MeshNode {
    fun onReceive(payload: String, from: MeshNode)
}
