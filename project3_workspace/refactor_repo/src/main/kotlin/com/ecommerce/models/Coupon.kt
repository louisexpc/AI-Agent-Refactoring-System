package com.ecommerce.models

import org.jetbrains.exposed.sql.Table
import org.jetbrains.exposed.sql.javatime.datetime
import java.time.LocalDateTime

data class Coupon(
    val id: Int,
    val code: String,
    val discountPercentage: Double,
    val expiryDate: LocalDateTime,
    val isActive: Boolean,
    val createdAt: LocalDateTime,
    val updatedAt: LocalDateTime
)

object Coupons : Table() {
    val id = integer("id").autoIncrement()
    val code = varchar("code", 255).uniqueIndex()
    val discountPercentage = double("discount_percentage")
    val expiryDate = datetime("expiry_date")
    val isActive = bool("is_active").default(true)
    val createdAt = datetime("created_at").default(LocalDateTime.now())
    val updatedAt = datetime("updated_at").default(LocalDateTime.now())

    override val primaryKey = PrimaryKey(id)
}
