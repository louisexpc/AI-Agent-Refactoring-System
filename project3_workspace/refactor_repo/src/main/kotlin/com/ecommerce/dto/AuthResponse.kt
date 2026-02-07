package com.ecommerce.dto

data class AuthResponse(
    val token: String,
    val refreshToken: String
)
