package com.example.ecommerce.controller

import com.example.ecommerce.model.Order
import io.ktor.http.*
import io.ktor.server.application.*
import io.ktor.server.request.*
import io.ktor.server.response.*
import io.ktor.server.routing.*

val orders = mutableListOf<Order>()

fun Route.orderRouting() {
    route("/orders") {
        get {
            if (orders.isNotEmpty()) {
                call.respond(orders)
            } else {
                call.respondText("No orders found", status = HttpStatusCode.OK)
            }
        }
        post {
            val order = call.receive<Order>()
            orders.add(order)
            call.respondText("Order created", status = HttpStatusCode.Created)
        }
        get("/{id}") {
            val id = call.parameters["id"] ?: return@get call.respond(HttpStatusCode.BadRequest)
            val order = orders.find { it.id == id.toInt() } ?: return@get call.respondText(
                "Not Found",
                status = HttpStatusCode.NotFound
            )
            call.respond(order)
        }
    }
}
