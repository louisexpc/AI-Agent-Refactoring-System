package com.ecommerce.features.cart.models

import kotlinx.serialization.Serializable

@Serializable
data class AddToCartRequest(val productId: Int, val quantity: Int)

@Serializable
data class UpdateCartItemRequest(val quantity: Int)
