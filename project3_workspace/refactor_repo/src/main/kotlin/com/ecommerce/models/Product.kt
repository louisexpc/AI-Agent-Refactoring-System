package com.ecommerce.models

import java.time.LocalDateTime

data class Product(
    val id: Int,
    val title: String,
    val price: Double,
    val description: String,
    val quantity: Int,
    val slug: String,
    val brand: String?,
    val categoryId: Int?,
    val sold: Int = 0,
    val discount: Double?,
    val images: List<String> = emptyList(),
    val totalRatings: Int = 0,
    val ratings: List<Rating> = emptyList(),
    val createdAt: LocalDateTime,
    val updatedAt: LocalDateTime
)

data class Rating(
    val stars: Int,
    val comment: String,
    val postedBy: Int
)
