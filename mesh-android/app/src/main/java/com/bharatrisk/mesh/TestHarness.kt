package com.bharatrisk.mesh

fun runMeshSimulation(): List<String> {
    val manager = MeshManager()
    val testPacket = MeshPacket(
        message_id = "SOS-SIM-001",
        emergency_type = "TRAPPED",
        latitude = 22.546,
        longitude = 88.438,
        people = 4,
        vulnerable = listOf("elderly", "infant"),
        priority = "CRITICAL"
    )
    return manager.simulateRoute(testPacket)
}

fun main() {
    println("=== Starting BharatRisk Mesh SOS Route Simulation ===")
    val results = runMeshSimulation()
    results.forEach { println(it) }
    println("=== Mesh SOS Simulation Completed Successfully ===")
}
