package com.ecommerce.models

import org.jetbrains.exposed.sql.Table

data class CartItem(
    val cartId: Int,
    val productId: Int,
    var quantity: Int
)

data class Cart(
    val id: Int,
    val userId: Int,
    val items: MutableList<CartItem> = mutableListOf()
)

object Carts : Table() {
    val id = integer("id").autoIncrement()
    val userId = integer("user_id").references(Users.id)

    override val primaryKey = PrimaryKey(id)
}

object CartItems : Table() {
    val id = integer("id").autoIncrement()
    val cartId = integer("cart_id").references(Carts.id)
    val productId = integer("product_id").references(Products.id)
    val quantity = integer("quantity")

    override val primaryKey = PrimaryKey(id)
}