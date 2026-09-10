package com.bharatrisk.mesh

import java.io.File

class MessageStore(private val storageDir: File? = null) {
    private val memorySeen = mutableSetOf<String>()
    private val memoryPending = mutableListOf<MeshPacket>()

    init {
        storageDir?.let { if (!it.exists()) it.mkdirs() }
    }

    fun hasSeen(messageId: String): Boolean {
        if (memorySeen.contains(messageId)) return true
        if (storageDir != null) {
            val f = File(storageDir, sanitize(messageId) + ".json")
            return f.exists()
        }
        return false
    }

    fun store(packet: MeshPacket) {
        memorySeen.add(packet.message_id)
        memoryPending.add(packet)
        if (storageDir != null) {
            val f = File(storageDir, sanitize(packet.message_id) + ".json")
            try {
                f.writeText(packet.toJson())
            } catch (_: Exception) {}
        }
    }

    fun getPending(): List<MeshPacket> {
        return memoryPending.toList()
    }

    fun remove(messageId: String) {
        memoryPending.removeAll { it.message_id == messageId }
        if (storageDir != null) {
            val f = File(storageDir, sanitize(messageId) + ".json")
            if (f.exists()) f.delete()
        }
    }

    private fun sanitize(s: String) = s.replace(Regex("[^A-Za-z0-9_\\-]"), "_")
}
