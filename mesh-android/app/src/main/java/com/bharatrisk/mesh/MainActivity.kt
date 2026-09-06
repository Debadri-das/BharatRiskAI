package com.bharatrisk.mesh

import android.app.Activity
import android.os.Bundle
import android.widget.TextView

class MainActivity : Activity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val events = MeshManager().simulateRoute().joinToString(separator = "\n")
        setContentView(TextView(this).apply {
            text = "BharatRisk Mesh SOS Prototype\n\n$events"
            textSize = 18f
            setPadding(32, 48, 32, 32)
        })
    }
}
