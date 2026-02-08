package com.ecommerce.security

import com.ecommerce.models.User
import io.jsonwebtoken.Jwts
import io.jsonwebtoken.SignatureAlgorithm
import org.springframework.beans.factory.annotation.Value
import org.springframework.stereotype.Component
import java.util.*

@Component
class JwtProvider {

    @Value("\${jwt.secret}")
    private lateinit var jwtSecret: String

    fun generateToken(user: User): String {
        val claims = Jwts.claims().setSubject(user.email)
        claims["id"] = user.id
        claims["role"] = user.role

        val now = Date()
        val validity = Date(now.time + 3600000) // 1 hour

        return Jwts.builder()
            .setClaims(claims)
            .setIssuedAt(now)
            .setExpiration(validity)
            .signWith(SignatureAlgorithm.HS256, jwtSecret)
            .compact()
    }

    fun generateRefreshToken(user: User): String {
        val now = Date()
        val validity = Date(now.time + 86400000) // 1 day

        return Jwts.builder()
            .setSubject(user.email)
            .setIssuedAt(now)
            .setExpiration(validity)
            .signWith(SignatureAlgorithm.HS256, jwtSecret)
            .compact()
    }

    fun getEmailFromToken(token: String): String {
        return Jwts.parser().setSigningKey(jwtSecret).parseClaimsJws(token).body.subject
    }

    fun validateToken(token: String): Boolean {
        try {
            Jwts.parser().setSigningKey(jwtSecret).parseClaimsJws(token)
            return true
        } catch (e: Exception) {
            // Log exception
        }
        return false
    }
}
