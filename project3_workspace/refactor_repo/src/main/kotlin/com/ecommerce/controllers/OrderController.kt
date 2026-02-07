package com.ecommerce.controllers

import com.ecommerce.dao.OrderDao
import com.ecommerce.models.Order
import io.ktor.http.* 
import io.ktor.server.application.*
import io.ktor.server.request.*
import io.ktor.server.response.*
import io.ktor.server.routing.*

fun Route.orderRouting(orderDao: OrderDao) {
    route("/orders") {
        post("/create") {
            val order = call.receive<Order>()
            val createdOrder = orderDao.create(order)
            call.respond(HttpStatusCode.Created, createdOrder)
        }

        post("/{id}/order-status") {
            val orderId = call.parameters["id"]?.toIntOrNull()
            if (orderId == null) {
                call.respond(HttpStatusCode.BadRequest, "Invalid order ID")
                return@post
            }
            val status = call.receive<String>()
            orderDao.updateStatus(orderId, status)
            call.respond(HttpStatusCode.OK, "Order status updated")
        }
    }
}