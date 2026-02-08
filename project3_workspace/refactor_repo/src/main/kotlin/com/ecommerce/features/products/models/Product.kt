package com.ecommerce.features.products.models

import java.time.LocalDateTime

// Base Product data class
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
    val images: List<String>?,
    val totalRatings: Int = 0,
    val createdAt: LocalDateTime,
    val updatedAt: LocalDateTime
)

// Request to create a new product
data class CreateProductRequest(
    val title: String,
    val price: Double,
    val description: String,
    val quantity: Int,
    val slug: String,
    val brand: String?,
    val categoryId: Int?,
    val discount: Double?,
    val images: List<String>?
)

// Request to update an existing product
data class UpdateProductRequest(
    val title: String?,
    val price: Double?,
    val description: String?,
    val quantity: Int?,
    val slug: String?,
    val brand: String?,
    val categoryId: Int?,
    val discount: Double?,
    val images: List<String>?
)

// Response for a single product
data class ProductResponse( 
    val id: Int,
    val title: String,
    val price: Double,
    val description: String,
    val quantity: Int,
    val slug: String,
    val brand: String?,
    val categoryId: Int?,
    val sold: Int,
    val discount: Double?,
    val images: List<String>?,
    val totalRatings: Int,
    val createdAt: String,
    val updatedAt: String
)
