package com.example.ecommerce.model

import java.time.LocalDateTime

data class Order(
    val id: Long? = null,
    val products: List<OrderItem> = emptyList(),
    val paymentIntent: Any? = null,
    val orderStatus: String = "Not Processed",
    val orderBy: Long, // UserId
    val createdAt: LocalDateTime = LocalDateTime.now(),
    val updatedAt: LocalDateTime = LocalDateTime.now()
)

data class OrderItem(
    val product: Long, // ProductId
    val count: Int,
    val color: String
)
