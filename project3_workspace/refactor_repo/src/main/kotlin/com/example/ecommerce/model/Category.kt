package com.example.ecommerce.model

import java.time.LocalDateTime

data class Category(
    val id: Long? = null,
    val title: String,
    val createdAt: LocalDateTime = LocalDateTime.now(),
    val updatedAt: LocalDateTime = LocalDateTime.now()
)
