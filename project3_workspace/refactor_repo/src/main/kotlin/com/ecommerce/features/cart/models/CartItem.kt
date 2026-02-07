package com.ecommerce.features.cart.models

import kotlinx.serialization.Serializable

@Serializable
data class CartItem(
    val id: Int,
    val cartId: Int,
    val productId: Int,
    val quantity: Int,
)
