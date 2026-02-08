package com.ecommerce.features.order

import com.ecommerce.features.order.models.Order
import com.ecommerce.features.order.models.OrderItem
import com.ecommerce.plugins.Database
import java.sql.Statement

class OrderRepository(private val db: Database) {

    suspend fun createOrder(userId: Int, status: String): Order {
        val sql = "INSERT INTO orders (user_id, status, created_at) VALUES (?, ?, NOW()) RETURNING id, user_id, status, created_at"
        return db.query {
            val statement = it.prepareStatement(sql, Statement.RETURN_GENERATED_KEYS)
            statement.setInt(1, userId)
            statement.setString(2, status)
            val resultSet = statement.executeQuery()
            if (resultSet.next()) {
                Order(
                    id = resultSet.getInt("id"),
                    userId = resultSet.getInt("user_id"),
                    status = resultSet.getString("status"),
                    createdAt = resultSet.getTimestamp("created_at").toLocalDateTime()
                )
            } else {
                throw Exception("Failed to create order")
            }
        }
    }

    suspend fun addOrderItem(orderId: Int, productId: Int, quantity: Int, price: Double): OrderItem {
        val sql = "INSERT INTO order_items (order_id, product_id, quantity, price) VALUES (?, ?, ?, ?) RETURNING id, order_id, product_id, quantity, price"
        return db.query {
            val statement = it.prepareStatement(sql, Statement.RETURN_GENERATED_KEYS)
            statement.setInt(1, orderId)
            statement.setInt(2, productId)
            statement.setInt(3, quantity)
            statement.setDouble(4, price)
            val resultSet = statement.executeQuery()
            if (resultSet.next()) {
                OrderItem(
                    id = resultSet.getInt("id"),
                    orderId = resultSet.getInt("order_id"),
                    productId = resultSet.getInt("product_id"),
                    quantity = resultSet.getInt("quantity"),
                    price = resultSet.getDouble("price")
                )
            } else {
                throw Exception("Failed to add order item")
            }
        }
    }

    suspend fun getOrdersByUserId(userId: Int): List<Order> {
        val sql = "SELECT id, user_id, status, created_at FROM orders WHERE user_id = ?"
        return db.query {
            val statement = it.prepareStatement(sql)
            statement.setInt(1, userId)
            val resultSet = statement.executeQuery()
            val orders = mutableListOf<Order>()
            while (resultSet.next()) {
                orders.add(
                    Order(
                        id = resultSet.getInt("id"),
                        userId = resultSet.getInt("user_id"),
                        status = resultSet.getString("status"),
                        createdAt = resultSet.getTimestamp("created_at").toLocalDateTime()
                    )
                )
            }
            orders
        }
    }

    suspend fun getOrderById(orderId: Int): Order? {
        val sql = "SELECT id, user_id, status, created_at FROM orders WHERE id = ?"
        return db.query {
            val statement = it.prepareStatement(sql)
            statement.setInt(1, orderId)
            val resultSet = statement.executeQuery()
            if (resultSet.next()) {
                Order(
                    id = resultSet.getInt("id"),
                    userId = resultSet.getInt("user_id"),
                    status = resultSet.getString("status"),
                    createdAt = resultSet.getTimestamp("created_at").toLocalDateTime()
                )
            } else {
                null
            }
        }
    }

    suspend fun getOrderItemsByOrderId(orderId: Int): List<OrderItem> {
        val sql = "SELECT id, order_id, product_id, quantity, price FROM order_items WHERE order_id = ?"
        return db.query {
            val statement = it.prepareStatement(sql)
            statement.setInt(1, orderId)
            val resultSet = statement.executeQuery()
            val orderItems = mutableListOf<OrderItem>()
            while (resultSet.next()) {
                orderItems.add(
                    OrderItem(
                        id = resultSet.getInt("id"),
                        orderId = resultSet.getInt("order_id"),
                        productId = resultSet.getInt("product_id"),
                        quantity = resultSet.getInt("quantity"),
                        price = resultSet.getDouble("price")
                    )
                )
            }
            orderItems
        }
    }
}
