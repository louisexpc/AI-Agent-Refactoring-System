package com.ecommerce.repository

import com.ecommerce.models.Order
import com.ecommerce.models.OrderItem
import java.sql.Connection
import java.sql.Statement

class OrderRepository(private val connection: Connection) {

    fun createOrder(order: Order): Order {
        val sql = "INSERT INTO orders (user_id, status, total_price) VALUES (?, ?, ?)"
        val stmt = connection.prepareStatement(sql, Statement.RETURN_GENERATED_KEYS)
        stmt.setInt(1, order.userId)
        stmt.setString(2, order.status)
        stmt.setBigDecimal(3, order.totalPrice)
        stmt.executeUpdate()

        val generatedKeys = stmt.generatedKeys
        if (generatedKeys.next()) {
            order.id = generatedKeys.getInt(1)
        }

        order.items.forEach { item ->
            createOrderItem(item, order.id)
        }

        return order
    }

    private fun createOrderItem(item: OrderItem, orderId: Int) {
        val sql = "INSERT INTO order_items (order_id, product_id, quantity, price) VALUES (?, ?, ?, ?)"
        val stmt = connection.prepareStatement(sql)
        stmt.setInt(1, orderId)
        stmt.setInt(2, item.productId)
        stmt.setInt(3, item.quantity)
        stmt.setBigDecimal(4, item.price)
        stmt.executeUpdate()
    }

    fun getOrdersByUserId(userId: Int): List<Order> {
        val sql = "SELECT * FROM orders WHERE user_id = ?"
        val stmt = connection.prepareStatement(sql)
        stmt.setInt(1, userId)
        val rs = stmt.executeQuery()

        val orders = mutableListOf<Order>()
        while (rs.next()) {
            orders.add(
                Order(
                    id = rs.getInt("id"),
                    userId = rs.getInt("user_id"),
                    status = rs.getString("status"),
                    totalPrice = rs.getBigDecimal("total_price"),
                    createdAt = rs.getTimestamp("created_at").toInstant(),
                    items = getOrderItemsByOrderId(rs.getInt("id"))
                )
            )
        }
        return orders
    }

    private fun getOrderItemsByOrderId(orderId: Int): List<OrderItem> {
        val sql = "SELECT * FROM order_items WHERE order_id = ?"
        val stmt = connection.prepareStatement(sql)
        stmt.setInt(1, orderId)
        val rs = stmt.executeQuery()

        val items = mutableListOf<OrderItem>()
        while (rs.next()) {
            items.add(
                OrderItem(
                    id = rs.getInt("id"),
                    orderId = rs.getInt("order_id"),
                    productId = rs.getInt("product_id"),
                    quantity = rs.getInt("quantity"),
                    price = rs.getBigDecimal("price")
                )
            )
        }
        return items
    }

    fun updateOrderStatus(orderId: Int, status: String): Boolean {
        val sql = "UPDATE orders SET status = ? WHERE id = ?"
        val stmt = connection.prepareStatement(sql)
        stmt.setString(1, status)
        stmt.setInt(2, orderId)
        return stmt.executeUpdate() > 0
    }
}
