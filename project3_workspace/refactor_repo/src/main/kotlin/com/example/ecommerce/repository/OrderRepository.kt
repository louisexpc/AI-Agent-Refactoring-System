package com.example.ecommerce.repository

import com.example.ecommerce.model.Order

class OrderRepository {

    fun save(order: Order): Order {
        //language=SQL
        val sql = "INSERT INTO orders (order_status, order_by) VALUES (?, ?)"
        // Execute SQL
        return order
    }

    fun findById(id: Long): Order? {
        //language=SQL
        val sql = "SELECT * FROM orders WHERE id = ?"
        // Execute SQL
        return null
    }

    fun findAllByUserId(userId: Long): List<Order> {
        //language=SQL
        val sql = "SELECT * FROM orders WHERE order_by = ?"
        // Execute SQL
        return emptyList()
    }

    fun update(order: Order): Order {
        //language=SQL
        val sql = "UPDATE orders SET order_status = ? WHERE id = ?"
        // Execute SQL
        return order
    }

    fun deleteById(id: Long) {
        //language=SQL
        val sql = "DELETE FROM orders WHERE id = ?"
        // Execute SQL
    }
}
