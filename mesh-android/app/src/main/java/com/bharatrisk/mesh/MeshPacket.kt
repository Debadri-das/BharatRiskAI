package com.bharatrisk.mesh

import org.json.JSONObject
import java.time.Instant

data class MeshPacket(
    val message_id: String,
    val type: String,
    val emergency_type: String,
    val latitude: Double,
    val longitude: Double,
    val people: Int,
    val vulnerable: List<String>,
    val priority: String,
    val created_at: String = Instant.now().toString(),
    var ttl: Int = 10,
    var hop_count: Int = 0,
    var signature: String? = null
) {
    fun toJson(): String {
        val o = JSONObject()
        o.put("message_id", message_id)
        o.put("type", type)
        o.put("emergency_type", emergency_type)
        o.put("latitude", latitude)
        o.put("longitude", longitude)
        o.put("people", people)
        o.put("vulnerable", vulnerable)
        o.put("priority", priority)
        o.put("created_at", created_at)
        o.put("ttl", ttl)
        o.put("hop_count", hop_count)
        if (signature != null) o.put("signature", signature)
        return o.toString()
    }

    companion object {
        fun fromJson(s: String): MeshPacket {
            val o = JSONObject(s)
            val pkt = MeshPacket(
                message_id = o.getString("message_id"),
                type = o.getString("type"),
                emergency_type = o.getString("emergency_type"),
                latitude = o.getDouble("latitude"),
                longitude = o.getDouble("longitude"),
                people = o.getInt("people"),
                vulnerable = o.getJSONArray("vulnerable").let { arr ->
                    List(arr.length()) { i -> arr.getString(i) }
                },
                priority = o.getString("priority"),
                created_at = o.getString("created_at"),
                ttl = o.getInt("ttl"),
                hop_count = o.getInt("hop_count"),
            )
            if (o.has("signature")) pkt.signature = o.getString("signature")
            return pkt
        }
    }
}
package com.bharatrisk.mesh

import org.json.JSONArray
import org.json.JSONObject
import java.time.Instant
import java.util.UUID

data class MeshPacket(
    val messageId: String = "SOS-${UUID.randomUUID()}",
    val type: String = "EMERGENCY",
    val emergencyType: String,
    val latitude: Double,
    val longitude: Double,
    val people: Int,
    val vulnerable: List<String>,
    val priority: String,
    val createdAt: String = Instant.now().toString(),
    val ttl: Int = 10,
    val hopCount: Int = 0,
    val signature: String = ""
) {
    fun toJson(): JSONObject = JSONObject()
        .put("message_id", messageId)
        .put("type", type)
        .put("emergency_type", emergencyType)
        .put("latitude", latitude)
        .put("longitude", longitude)
        .put("people", people)
        .put("vulnerable", JSONArray(vulnerable))
        .put("priority", priority)
        .put("created_at", createdAt)
        .put("ttl", ttl)
        .put("hop_count", hopCount)
        .put("signature", signature)

    fun forwarded(): MeshPacket = copy(ttl = ttl - 1, hopCount = hopCount + 1)

    companion object {
        fun fromJson(json: JSONObject): MeshPacket = MeshPacket(
            messageId = json.getString("message_id"),
            type = json.optString("type", "EMERGENCY"),
            emergencyType = json.getString("emergency_type"),
            latitude = json.getDouble("latitude"),
            longitude = json.getDouble("longitude"),
            people = json.getInt("people"),
            vulnerable = (0 until json.optJSONArray("vulnerable")!!.length()).map { json.optJSONArray("vulnerable")!!.getString(it) },
            priority = json.getString("priority"),
            createdAt = json.getString("created_at"),
            ttl = json.getInt("ttl"),
            hopCount = json.getInt("hop_count"),
            signature = json.optString("signature", "")
        )
    }
}
