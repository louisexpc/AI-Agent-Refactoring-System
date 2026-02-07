package com.ecommerce.features.order.models

data class OrderItem(
    val id: Int,
    val orderId: Int,
    val productId: Int,
    val quantity: Int,
    val price: Double
)
