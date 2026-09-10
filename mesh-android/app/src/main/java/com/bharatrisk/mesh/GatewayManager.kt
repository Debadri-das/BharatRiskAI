package com.bharatrisk.mesh

import java.net.HttpURLConnection
import java.net.URL
import java.nio.charset.StandardCharsets
import org.json.JSONArray
import org.json.JSONObject

class GatewayManager(private val serverBase: String = "http://localhost:8000") {
    fun hasConnectivity(): Boolean {
        return try {
            val u = URL("$serverBase/api/health")
            val c = u.openConnection() as HttpURLConnection
            c.connectTimeout = 1200
            c.readTimeout = 1200
            c.requestMethod = "GET"
            c.responseCode == 200
        } catch (ex: Exception) {
            false
        }
    }

    fun forward(packet: MeshPacket): Boolean {
        return try {
            val endpoint = URL("$serverBase/api/emergency")
            val conn = endpoint.openConnection() as HttpURLConnection
            conn.requestMethod = "POST"
            conn.doOutput = true
            conn.setRequestProperty("Content-Type", "application/json")
            val body = JSONObject().apply {
                put("message_id", packet.message_id)
                put("emergency_type", packet.emergency_type)
                put("latitude", packet.latitude)
                put("longitude", packet.longitude)
                put("people", packet.people)
                put("vulnerable", JSONArray(packet.vulnerable))
                put("description", "Forwarded SOS via Mesh Node")
            }.toString()
            conn.outputStream.use { os -> os.write(body.toByteArray(StandardCharsets.UTF_8)) }
            conn.responseCode in 200..299
        } catch (ex: Exception) {
            false
        }
    }
}
