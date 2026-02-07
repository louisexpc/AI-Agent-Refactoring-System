package com.ecommerce.dto

data class RegisterRequest(
    val firstName: String,
    val lastName: String,
    val email: String,
    val mobile: String,
    val password: String
)
