package com.ecommerce.models

import java.time.LocalDateTime

data class Category(
    val id: Int,
    val title: String,
    val products: List<Int> = emptyList(),
    val createdAt: LocalDateTime,
    val updatedAt: LocalDateTime
)
