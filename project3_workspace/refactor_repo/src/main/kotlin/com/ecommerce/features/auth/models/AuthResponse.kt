
package com.ecommerce.features.auth.models

import kotlinx.serialization.Serializable

@Serializable
data class UserLoginResponse(
    val accessToken: String,
    val refreshToken: String
)
