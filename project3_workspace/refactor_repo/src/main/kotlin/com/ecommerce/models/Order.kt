package com.ecommerce.models

import org.jetbrains.exposed.sql.Table
import java.math.BigDecimal

data class OrderItem(
    val id: Int,
    val orderId: Int,
    val productId: Int,
    val quantity: Int,
    val price: BigDecimal
)

data class Order(
    val id: Int,
    val userId: Int,
    val items: List<OrderItem>,
    val shippingAddress: String,
    val paymentMethod: String,
    val shippingPrice: BigDecimal,
    val totalPrice: BigDecimal,
    val status: String
)

object Orders : Table() {
    val id = integer("id").autoIncrement()
    val userId = integer("user_id").references(Users.id)
    val shippingAddress = varchar("shipping_address", 255)
    val paymentMethod = varchar("payment_method", 255)
    val shippingPrice = decimal("shipping_price", 10, 2)
    val totalPrice = decimal("total_price", 10, 2)
    val status = varchar("status", 50)

    override val primaryKey = PrimaryKey(id)
}

object OrderItems : Table() {
    val id = integer("id").autoIncrement()
    val orderId = integer("order_id").references(Orders.id)
    val productId = integer("product_id").references(Products.id)
    val quantity = integer("quantity")
    val price = decimal("price", 10, 2)

    override val primaryKey = PrimaryKey(id)
}