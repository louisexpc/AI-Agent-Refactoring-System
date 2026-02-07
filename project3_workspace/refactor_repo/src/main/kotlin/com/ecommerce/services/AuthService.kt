package com.ecommerce.services

import com.ecommerce.dto.AuthResponse
import com.ecommerce.dto.LoginRequest
import com.ecommerce.dto.RegisterRequest
import com.ecommerce.models.User
import com.ecommerce.repositories.UserRepository
import com.ecommerce.security.JwtProvider
import org.springframework.security.crypto.password.PasswordEncoder
import org.springframework.stereotype.Service

@Service
class AuthService(
    private val userRepository: UserRepository,
    private val passwordEncoder: PasswordEncoder,
    private val jwtProvider: JwtProvider
) {

    fun register(registerRequest: RegisterRequest): User {
        if (userRepository.findByEmail(registerRequest.email) != null) {
            throw RuntimeException("User already exists")
        }
        val user = User(
            firstName = registerRequest.firstName,
            lastName = registerRequest.lastName,
            email = registerRequest.email,
            mobile = registerRequest.mobile,
            password = passwordEncoder.encode(registerRequest.password)
        )
        return userRepository.save(user)
    }

    fun login(loginRequest: LoginRequest): AuthResponse {
        val user = userRepository.findByEmail(loginRequest.email) ?: throw RuntimeException("User not found")
        if (!passwordEncoder.matches(loginRequest.password, user.password)) {
            throw RuntimeException("Invalid credentials")
        }
        val token = jwtProvider.generateToken(user)
        val refreshToken = jwtProvider.generateRefreshToken(user)
        return AuthResponse(token, refreshToken)
    }
}
