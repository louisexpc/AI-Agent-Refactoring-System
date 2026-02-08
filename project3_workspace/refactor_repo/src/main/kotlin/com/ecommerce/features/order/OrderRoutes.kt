package com.ecommerce.features.order

import com.ecommerce.features.order.models.OrderRequest
import io.ktor.server.application.*
import io.ktor.server.auth.*
import io.ktor.server.auth.jwt.*
import io.ktor.server.request.*
import io.ktor.server.response.*
import io.ktor.server.routing.*

fun Route.orderRoutes(orderService: OrderService) {
    authenticate {
        route("/orders") {
            post {
                val principal = call.principal<JWTPrincipal>()
                val userId = principal?.payload?.getClaim("userId")?.asInt() ?: throw Exception("User not found")
                val orderRequest = call.receive<OrderRequest>()
                val order = orderService.createOrder(userId, orderRequest)
                call.respond(order)
            }

            get {
                val principal = call.principal<JWTPrincipal>()
                val userId = principal?.payload?.getClaim("userId")?.asInt() ?: throw Exception("User not found")
                val orders = orderService.getOrdersForUser(userId)
                call.respond(orders)
            }

            get("/{id}") {
                val orderId = call.parameters["id"]?.toIntOrNull() ?: throw Exception("Invalid order ID")
                val order = orderService.getOrder(orderId)
                if (order != null) {
                    call.respond(order)
                } else {
                    call.respondText("Order not found", status = io.ktor.http.HttpStatusCode.NotFound)
                }
            }
        }
    }
}
