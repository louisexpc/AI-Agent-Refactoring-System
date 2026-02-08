package com.example.ecommerce.model

import java.time.LocalDate
import java.time.LocalDateTime

data class Coupon(
    val id: Long? = null,
    val name: String,
    val expiry: LocalDate,
    val discount: Double,
    val createdAt: LocalDateTime = LocalDateTime.now(),
    val updatedAt: LocalDateTime = LocalDateTime.now()
)
