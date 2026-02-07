package com.ecommerce.features.order.models

import java.time.LocalDateTime


data class OrderRequest(
    val products: List<OrderItemRequest>
)

data class OrderItemRequest(
    val productId: Int,
    val quantity: Int
)

data class OrderResponse(
    val id: Int,
    val userId: Int,
    val status: String,
    val createdAt: LocalDateTime,
    val items: List<OrderItemResponse>
)

data class OrderItemResponse(
    val productId: Int,
    val quantity: Int,
    val price: Double
)
