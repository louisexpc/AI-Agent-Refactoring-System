
package com.ecommerce.features.auth.models

import kotlinx.serialization.Serializable

@Serializable
data class UserProfileResponse(
    val id: Int,
    val firstName: String,
    val lastName: String,
    val email: String,
    val mobile: String,
    val role: String
)
