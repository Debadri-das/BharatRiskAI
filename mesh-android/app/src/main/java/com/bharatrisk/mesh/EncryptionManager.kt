package com.bharatrisk.mesh

import java.security.SecureRandom
import javax.crypto.Mac
import javax.crypto.spec.SecretKeySpec
import java.util.Base64

object EncryptionManager {
    private var key: ByteArray? = null

    fun getOrCreateKey(): ByteArray {
        if (key == null) {
            val rnd = SecureRandom()
            val k = ByteArray(32)
            rnd.nextBytes(k)
            key = k
        }
        return key!!
    }

    fun sign(payload: String): String {
        val k = getOrCreateKey()
        val mac = Mac.getInstance("HmacSHA256")
        mac.init(SecretKeySpec(k, "HmacSHA256"))
        val sig = mac.doFinal(payload.toByteArray(Charsets.UTF_8))
        return Base64.getUrlEncoder().withoutPadding().encodeToString(sig)
    }

    fun verify(payload: String, signature: String): Boolean {
        val expected = sign(payload)
        return expected == signature
    }
}
