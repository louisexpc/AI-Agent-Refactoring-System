package com.example.ecommerce.model

import java.time.LocalDateTime

data class Cart(
    val id: Long? = null,
    val products: List<CartItem> = emptyList(),
    val cartTotal: Double,
    val totalAfterDiscount: Double? = null,
    val orderBy: Long, // UserId
    val createdAt: LocalDateTime = LocalDateTime.now(),
    val updatedAt: LocalDateTime = LocalDateTime.now()
)

data class CartItem(
    val product: Long, // ProductId
    val count: Int,
    val color: String,
    val price: Double
)
