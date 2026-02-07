
package com.ecommerce.features.auth.models

import java.time.LocalDateTime

data class User(
    val id: Int,
    val firstName: String,
    val lastName: String,
    val email: String,
    val mobile: String,
    val passwordHash: String,
    val role: String = "user",
    val isBlocked: Boolean = false,
    val passwordChangedAt: LocalDateTime? = null,
    val passwordResetToken: String? = null,
    val passwordResetExpires: LocalDateTime? = null
)
