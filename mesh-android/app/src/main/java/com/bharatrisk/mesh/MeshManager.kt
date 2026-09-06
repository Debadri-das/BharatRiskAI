package com.bharatrisk.mesh

import java.io.File

/**
 * High-level manager that ties discovery, routing and gateway together.
 * For demo/test purposes this is initialized with a SimulatedTransport and storage path.
 */
class MeshManager(
    private val nodeId: String,
    private val transport: SimulatedTransport,
    private val storageDir: File,
    private val serverBase: String
) {
    private val store = MessageStore(storageDir)
    private val gateway = GatewayManager(serverBase)
    private lateinit var router: MessageRouter
    private val node = object : MeshNode {
        override fun onReceive(payload: String, from: MeshNode) {
            router.onReceive(payload, from)
        }
    }

    init {
        router = MessageRouter(store, gateway, transport, node)
        transport.register(router)
    }

    fun sendSOS(packet: MeshPacket) {
        router.originateAndSend(packet)
    }

    fun shutdown() {
        // cleanup if necessary
    }
}
