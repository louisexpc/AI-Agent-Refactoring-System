package com.ecommerce.dao

import com.ecommerce.models.Order

interface OrderDao {
    suspend fun create(order: Order): Order
    suspend fun getById(orderId: Int): Order?
    suspend fun updateStatus(orderId: Int, status: String)
}
