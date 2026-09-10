package com.bharatrisk.mesh

import org.json.JSONArray
import org.json.JSONObject
import java.time.Instant
import java.util.UUID

data class MeshPacket(
    val message_id: String = "SOS-${UUID.randomUUID().toString().take(8).uppercase()}",
    val type: String = "EMERGENCY",
    val emergency_type: String = "TRAPPED",
    val latitude: Double = 22.546,
    val longitude: Double = 88.438,
    val people: Int = 1,
    val vulnerable: List<String> = emptyList(),
    val priority: String = "CRITICAL",
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
        o.put("vulnerable", JSONArray(vulnerable))
        o.put("priority", priority)
        o.put("created_at", created_at)
        o.put("ttl", ttl)
        o.put("hop_count", hop_count)
        if (signature != null) o.put("signature", signature)
        return o.toString()
    }

    fun forwarded(node: String): MeshPacket = copy(
        ttl = ttl - 1,
        hop_count = hop_count + 1
    )

    companion object {
        fun fromJson(s: String): MeshPacket {
            val o = JSONObject(s)
            val pkt = MeshPacket(
                message_id = o.optString("message_id", "SOS-UNKNOWN"),
                type = o.optString("type", "EMERGENCY"),
                emergency_type = o.optString("emergency_type", "TRAPPED"),
                latitude = o.optDouble("latitude", 22.546),
                longitude = o.optDouble("longitude", 88.438),
                people = o.optInt("people", 1),
                vulnerable = o.optJSONArray("vulnerable")?.let { arr ->
                    List(arr.length()) { i -> arr.getString(i) }
                } ?: emptyList(),
                priority = o.optString("priority", "CRITICAL"),
                created_at = o.optString("created_at", Instant.now().toString()),
                ttl = o.optInt("ttl", 10),
                hop_count = o.optInt("hop_count", 0),
            )
            if (o.has("signature")) pkt.signature = o.getString("signature")
            return pkt
        }
    }
}
