package com.ecommerce.features.cart.models

import kotlinx.serialization.Serializable

@Serializable
data class Cart(
    val id: Int,
    val userId: Int,
)
