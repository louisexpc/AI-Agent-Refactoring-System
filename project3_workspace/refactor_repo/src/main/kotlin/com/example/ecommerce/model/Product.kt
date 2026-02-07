package com.example.ecommerce.model

import java.time.LocalDateTime

data class Product(
    val id: Long? = null,
    val title: String,
    val slug: String,
    val description: String,
    val price: Double,
    val category: String,
    val brand: String,
    val quantity: Int,
    val sold: Int = 0,
    val images: List<String> = emptyList(),
    val color: String,
    val ratings: List<Rating> = emptyList(),
    val totalRating: Double = 0.0,
    val createdAt: LocalDateTime = LocalDateTime.now(),
    val updatedAt: LocalDateTime = LocalDateTime.now()
)

data class Rating(
    val star: Int,
    val postedBy: Long // UserId
)
