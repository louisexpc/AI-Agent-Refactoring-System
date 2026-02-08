package com.ecommerce.routes

import com.ecommerce.models.Order
import com.ecommerce.repository.OrderRepository
import io.ktor.http.*
import io.ktor.server.application.*
import io.ktor.server.auth.*
import io.ktor.server.auth.jwt.*
import io.ktor.server.request.*
import io.ktor.server.response.*
import io.ktor.server.routing.*

fun Route.orderRoutes(orderRepository: OrderRepository) {
    authenticate {
        route("/orders") {
            post {
                val order = call.receive<Order>()
                val principal = call.principal<JWTPrincipal>()
                val userId = principal!!.payload.getClaim("userId").asInt()
                val createdOrder = orderRepository.createOrder(order.copy(userId = userId))
                call.respond(HttpStatusCode.Created, createdOrder)
            }

            get {
                val principal = call.principal<JWTPrincipal>()
                val userId = principal!!.payload.getClaim("userId").asInt()
                val orders = orderRepository.getOrdersByUserId(userId)
                call.respond(orders)
            }

            put("/{id}/status") {
                val orderId = call.parameters["id"]?.toIntOrNull()
                if (orderId == null) {
                    call.respond(HttpStatusCode.BadRequest, "Invalid order ID")
                    return@put
                }
                val status = call.receive<String>()
                val updated = orderRepository.updateOrderStatus(orderId, status)
                if (updated) {
                    call.respond(HttpStatusCode.OK)
                } else {
                    call.respond(HttpStatusCode.NotFound)
                }
            }
        }
    }
}
