package com.ecommerce.models

import java.time.LocalDateTime

data class User(
    val id: Int,
    val firstName: String,
    val lastName: String,
    val email: String,
    val mobile: String,
    var passwordHash: String,
    var passwordChangedAt: LocalDateTime?,
    var passwordResetToken: String?,
    var passwordResetExpires: LocalDateTime?,
    val role: String = "user",
    val isBlocked: Boolean = false,
    val cart: List<Int> = emptyList(),
    val wishlist: List<Int> = emptyList()
)
