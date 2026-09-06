package com.bharatrisk.mesh

import com.sun.net.httpserver.HttpExchange
import com.sun.net.httpserver.HttpHandler
import com.sun.net.httpserver.HttpServer
import java.io.File
import java.io.InputStream
import java.net.InetSocketAddress
import java.time.Instant
import kotlin.concurrent.thread

fun main() {
    // Start a simple HTTP server to act as gateway endpoint
    val port = 8001
    val server = HttpServer.create(InetSocketAddress(port), 0)
    server.createContext("/api/health", HttpHandler { exchange ->
        val resp = "{\"status\":\"ok\"}"
        exchange.sendResponseHeaders(200, resp.toByteArray().size.toLong())
        exchange.responseBody.use { it.write(resp.toByteArray()) }
    })
    server.createContext("/api/emergency", HttpHandler { exchange ->
        val body = exchange.requestBody.reader().readText()
        println("[GatewayServer] Received emergency POST: $body")
        val resp = "{\"ok\":true}"
        exchange.sendResponseHeaders(200, resp.toByteArray().size.toLong())
        exchange.responseBody.use { it.write(resp.toByteArray()) }
    })
    thread { server.start(); println("[GatewayServer] Listening on http://localhost:$port") }

    val transport = SimulatedTransport()

    val baseTmp = File(System.getProperty("java.io.tmpdir"))
    val aDir = File(baseTmp, "meshA"); if (!aDir.exists()) aDir.mkdirs()
    val bDir = File(baseTmp, "meshB"); if (!bDir.exists()) bDir.mkdirs()
    val cDir = File(baseTmp, "meshC"); if (!cDir.exists()) cDir.mkdirs()

    val nodeA = MeshManager("A", transport, aDir, "http://localhost:$port")
    val nodeB = MeshManager("B", transport, bDir, "http://localhost:$port")
    val nodeC = MeshManager("C", transport, cDir, "http://localhost:$port")

    // create packet from A
    val pkt = MeshPacket(
        message_id = "SOS-TEST-001",
        type = "EMERGENCY",
        emergency_type = "TRAPPED",
        latitude = 22.546,
        longitude = 88.438,
        people = 4,
        vulnerable = listOf("elderly"),
        priority = "CRITICAL",
        created_at = Instant.now().toString(),
        ttl = 3,
        hop_count = 0
    )

    println("[Test] Originating packet from A: ${pkt.message_id}")
    nodeA.sendSOS(pkt)

    // wait for propagation
    Thread.sleep(3000)

    // show stores
    fun listStore(dir: File, name: String) {
        println("[Store:$name] files=${dir.listFiles()?.map { it.name } ?: emptyList<String>()}")
        dir.listFiles()?.forEach { f -> println("[Store:$name] ${f.name} -> ${f.readText()}") }
    }

    listStore(aDir, "A")
    listStore(bDir, "B")
    listStore(cDir, "C")

    println("[Test] Done. Stopping gateway server.")
    server.stop(0)
}
