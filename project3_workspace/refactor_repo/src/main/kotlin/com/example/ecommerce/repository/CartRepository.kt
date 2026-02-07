package com.example.ecommerce.repository

import com.example.ecommerce.model.Cart

class CartRepository {

    fun save(cart: Cart): Cart {
        //language=SQL
        val sql = "INSERT INTO carts (cart_total, total_after_discount, order_by) VALUES (?, ?, ?)"
        // Execute SQL
        return cart
    }

    fun findById(id: Long): Cart? {
        //language=SQL
        val sql = "SELECT * FROM carts WHERE id = ?"
        // Execute SQL
        return null
    }

    fun findByUserId(userId: Long): Cart? {
        //language=SQL
        val sql = "SELECT * FROM carts WHERE order_by = ?"
        // Execute SQL
        return null
    }

    fun update(cart: Cart): Cart {
        //language=SQL
        val sql = "UPDATE carts SET cart_total = ?, total_after_discount = ? WHERE id = ?"
        // Execute SQL
        return cart
    }

    fun deleteById(id: Long) {
        //language=SQL
        val sql = "DELETE FROM carts WHERE id = ?"
        // Execute SQL
    }
}
