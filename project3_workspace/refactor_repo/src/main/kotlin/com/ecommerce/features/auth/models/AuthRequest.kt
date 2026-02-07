
package com.ecommerce.features.auth.models

import kotlinx.serialization.Serializable

@Serializable
data class UserRegistrationRequest(
    val firstName: String,
    val lastName: String,
    val email: String,
    val mobile: String,
    val password: String
)

@Serializable
data class UserLoginRequest(
    val email: String,
    val password: String
)
