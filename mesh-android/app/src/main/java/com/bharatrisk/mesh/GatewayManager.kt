package com.bharatrisk.mesh

import java.net.HttpURLConnection
import java.net.URL
import java.nio.charset.StandardCharsets

class GatewayManager(private val serverBase: String) {
    fun hasConnectivity(): Boolean {
        return try {
            val u = URL(serverBase + "/api/health")
            val c = u.openConnection() as HttpURLConnection
            c.connectTimeout = 1200
            c.readTimeout = 1200
            c.requestMethod = "GET"
            val code = c.responseCode
            code == 200
        } catch (ex: Exception) {
            false
        }
    }

    fun forward(packet: MeshPacket) {
        val endpoint = URL(serverBase + "/api/emergency")
        val conn = endpoint.openConnection() as HttpURLConnection
        conn.requestMethod = "POST"
        conn.doOutput = true
        conn.setRequestProperty("Content-Type", "application/json")
        val body = org.json.JSONObject().apply {
            put("emergency_type", packet.emergency_type)
            put("latitude", packet.latitude)
            put("longitude", packet.longitude)
            put("people", packet.people)
            put("vulnerable", org.json.JSONArray(packet.vulnerable))
            put("description", "Forwarded SOS ${packet.message_id}")
        }.toString()
        conn.outputStream.use { os -> os.write(body.toByteArray(StandardCharsets.UTF_8)) }
        val code = conn.responseCode
        if (code !in 200..299) throw RuntimeException("gateway forward failed: $code")
    }
}
package com.bharatrisk.mesh

class GatewayManager {
    fun canReachServer(): Boolean = true
    fun upload(packet: MeshPacket): Boolean = canReachServer() && packet.ttl >= 0
}
