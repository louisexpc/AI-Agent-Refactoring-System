package com.example.ecommerce.security

import com.example.ecommerce.model.User
import io.jsonwebtoken.Claims
import io.jsonwebtoken.Jwts
import io.jsonwebtoken.SignatureAlgorithm
import org.springframework.beans.factory.annotation.Value
import org.springframework.stereotype.Component
import java.util.Date

@Component
class JwtTokenProvider {

    @Value("${'$'}{jwt.secret}")
    private lateinit var jwtSecret: String

    @Value("${'$'}{jwt.expirationMs}")
    private lateinit var jwtExpirationMs: String

    fun generateToken(user: User): String {
        val claims: MutableMap<String, Any> = HashMap()
        claims["id"] = user.id
        claims["email"] = user.email
        claims["role"] = user.role
        return createToken(claims, user.email)
    }

    private fun createToken(claims: Map<String, Any>, subject: String): String {
        val now = Date()
        val expiration = Date(now.time + jwtExpirationMs.toLong())
        return Jwts.builder()
                .setClaims(claims)
                .setSubject(subject)
                .setIssuedAt(now)
                .setExpiration(expiration)
                .signWith(SignatureAlgorithm.HS512, jwtSecret)
                .compact()
    }

    fun getClaimsFromToken(token: String): Claims {
        return Jwts.parser().setSigningKey(jwtSecret).parseClaimsJws(token).body
    }

    fun validateToken(token: String): Boolean {
        try {
            Jwts.parser().setSigningKey(jwtSecret).parseClaimsJws(token)
            return true
        } catch (ex: Exception) {
            return false
        }
    }
}
