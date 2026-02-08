
package com.ecommerce.features.auth.models

import kotlinx.serialization.Serializable

@Serializable
data class UserProfileUpdateRequest(
    val firstName: String? = null,
    val lastName: String? = null,
    val mobile: String? = null
)
