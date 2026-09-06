package com.bharatrisk.mesh

import java.io.File
import java.nio.file.Files
import java.nio.file.StandardOpenOption

class MessageStore(private val storageDir: File) {
    init {
        if (!storageDir.exists()) storageDir.mkdirs()
    }

    fun hasSeen(messageId: String): Boolean {
        val f = File(storageDir, sanitize(messageId) + ".json")
        return f.exists()
    }

    fun store(packet: MeshPacket) {
        val f = File(storageDir, sanitize(packet.message_id) + ".json")
        Files.writeString(f.toPath(), packet.toJson(), StandardOpenOption.CREATE, StandardOpenOption.TRUNCATE_EXISTING)
    }

    fun getPending(): List<MeshPacket> {
        return storageDir.listFiles { f -> f.name.endsWith(".json") }?.mapNotNull { f ->
            try {
                val s = Files.readString(f.toPath())
                MeshPacket.fromJson(s)
            } catch (ex: Exception) {
                null
            }
        } ?: emptyList()
    }

    fun remove(messageId: String) {
        val f = File(storageDir, sanitize(messageId) + ".json")
        if (f.exists()) f.delete()
    }

    private fun sanitize(s: String) = s.replace(Regex("[^A-Za-z0-9_\-]"), "_")
}
package com.bharatrisk.mesh

class MessageStore {
    private val seen = mutableSetOf<String>()
    private val messages = mutableListOf<MeshPacket>()

    fun hasSeen(messageId: String): Boolean = seen.contains(messageId)
    fun save(packet: MeshPacket) {
        seen.add(packet.messageId)
        messages.add(packet)
    }
    fun pending(): List<MeshPacket> = messages.toList()
}
