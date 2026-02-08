package com.example.ecommerce.model

import java.time.LocalDateTime

data class User(
    val id: Long? = null,
    val firstname: String,
    val lastname: String,
    val email: String,
    val mobile: String,
    val passwordHash: String,
    val role: String = "user",
    val isBlocked: Boolean = false,
    val cart: Cart? = null,
    val address: String? = null,
    val wishlist: List<Product> = emptyList(),
    val refreshToken: String? = null,
    val passwordChangedAt: LocalDateTime? = null,
    val passwordResetToken: String? = null,
    val passwordResetExpires: LocalDateTime? = null,
    val createdAt: LocalDateTime = LocalDateTime.now(),
    val updatedAt: LocalDateTime = LocalDateTime.now()
)
