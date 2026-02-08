package com.ecommerce.features.order.models

import java.time.LocalDateTime

data class Order(
    val id: Int,
    val userId: Int,
    val status: String,
    val createdAt: LocalDateTime
)
