package com.ecommerce.features.products.models

import java.time.LocalDateTime

// Base Category data class
data class Category(
    val id: Int,
    val title: String,
    val createdAt: LocalDateTime,
    val updatedAt: LocalDateTime
)

// Request to create a new category
data class CreateCategoryRequest(
    val title: String
)

// Request to update an existing category
data class UpdateCategoryRequest(
    val title: String
)

// Response for a single category
data class CategoryResponse(
    val id: Int,
    val title: String,
    val createdAt: String,
    val updatedAt: String
)
