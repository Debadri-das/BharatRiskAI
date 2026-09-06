package com.bharatrisk.mesh

class WebBridge {
    fun packetForDashboard(packet: MeshPacket): String = packet.toJson().toString()
}
