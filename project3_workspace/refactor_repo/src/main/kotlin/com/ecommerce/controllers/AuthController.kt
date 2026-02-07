package com.ecommerce.controllers

import com.ecommerce.dto.AuthResponse
import com.ecommerce.dto.LoginRequest
import com.ecommerce.dto.RegisterRequest
import com.ecommerce.services.AuthService
import org.springframework.http.ResponseEntity
import org.springframework.web.bind.annotation.PostMapping
import org.springframework.web.bind.annotation.RequestBody
import org.springframework.web.bind.annotation.RequestMapping
import org.springframework.web.bind.annotation.RestController

@RestController
@RequestMapping("/api/auth")
class AuthController(private val authService: AuthService) {

    @PostMapping("/register")
    fun register(@RequestBody registerRequest: RegisterRequest): ResponseEntity<Any> {
        return try {
            val user = authService.register(registerRequest)
            ResponseEntity.ok(user)
        } catch (e: RuntimeException) {
            ResponseEntity.badRequest().body(e.message)
        }
    }

    @PostMapping("/login")
    fun login(@RequestBody loginRequest: LoginRequest): ResponseEntity<AuthResponse> {
        return try {
            val authResponse = authService.login(loginRequest)
            ResponseEntity.ok(authResponse)
        } catch (e: RuntimeException) {
            ResponseEntity.badRequest().build()
        }
    }
}
