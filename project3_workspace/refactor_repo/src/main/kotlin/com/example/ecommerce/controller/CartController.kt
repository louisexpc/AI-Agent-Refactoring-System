package com.example.ecommerce.controller

import com.example.ecommerce.model.Cart
import com.example.ecommerce.model.Product
import io.ktor.http.*
import io.ktor.server.application.*
import io.ktor.server.request.*
import io.ktor.server.response.*
import io.ktor.server.routing.*

val cart = Cart(mutableListOf())

fun Route.cartRouting() {
    route("/cart") {
        get {
            if (cart.products.isNotEmpty()) {
                call.respond(cart)
            } else {
                call.respondText("Cart is empty", status = HttpStatusCode.OK)
            }
        }
        post {
            val product = call.receive<Product>()
            cart.products.add(product)
            call.respondText("Product added to cart", status = HttpStatusCode.Created)
        }
        delete("/{id}") {
            val id = call.parameters["id"] ?: return@delete call.respond(HttpStatusCode.BadRequest)
            if (cart.products.removeIf { it.id == id.toInt() }) {
                call.respondText("Product removed from cart", status = HttpStatusCode.OK)
            } else {
                call.respondText("Not Found", status = HttpStatusCode.NotFound)
            }
        }
    }
}
