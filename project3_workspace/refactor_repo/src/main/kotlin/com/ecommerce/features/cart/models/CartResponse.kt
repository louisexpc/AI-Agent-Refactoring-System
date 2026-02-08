package com.ecommerce.features.cart.models

import com.ecommerce.features.product.Product
import kotlinx.serialization.Serializable

@Serializable
data class CartResponse(
    val id: Int,
    val userId: Int,
    val items: List<CartItemResponse>
)

@Serializable
data class CartItemResponse(
    val product: Product,
    val quantity: Int
)
