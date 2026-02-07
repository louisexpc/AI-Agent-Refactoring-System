package com.ecommerce.features.order

import com.ecommerce.features.order.models.OrderRequest
import com.ecommerce.features.order.models.OrderResponse
import com.ecommerce.features.order.models.OrderItemResponse
import com.ecommerce.features.product.ProductRepository

class OrderService(private val orderRepository: OrderRepository, private val productRepository: ProductRepository) {

    suspend fun createOrder(userId: Int, orderRequest: OrderRequest): OrderResponse {
        val order = orderRepository.createOrder(userId, "Pending")

        val orderItems = orderRequest.products.map { item ->
            val product = productRepository.getProductById(item.productId) ?: throw Exception("Product not found")
            orderRepository.addOrderItem(order.id, item.productId, item.quantity, product.price)
        }

        return OrderResponse(
            id = order.id,
            userId = order.userId,
            status = order.status,
            createdAt = order.createdAt,
            items = orderItems.map { OrderItemResponse(it.productId, it.quantity, it.price) }
        )
    }

    suspend fun getOrdersForUser(userId: Int): List<OrderResponse> {
        val orders = orderRepository.getOrdersByUserId(userId)
        return orders.map { order ->
            val orderItems = orderRepository.getOrderItemsByOrderId(order.id)
            OrderResponse(
                id = order.id,
                userId = order.userId,
                status = order.status,
                createdAt = order.createdAt,
                items = orderItems.map { OrderItemResponse(it.productId, it.quantity, it.price) }
            )
        }
    }

    suspend fun getOrder(orderId: Int): OrderResponse? {
        val order = orderRepository.getOrderById(orderId) ?: return null
        val orderItems = orderRepository.getOrderItemsByOrderId(orderId)

        return OrderResponse(
            id = order.id,
            userId = order.userId,
            status = order.status,
            createdAt = order.createdAt,
            items = orderItems.map { OrderItemResponse(it.productId, it.quantity, it.price) }
        )
    }
}
