package com.ecommerce.routes

import com.ecommerce.repository.CartRepository
import io.ktor.http.*
import io.ktor.server.application.*
import io.ktor.server.request.*
import io.ktor.server.response.*
import io.ktor.server.routing.*

fun Route.cartRoutes(cartRepository: CartRepository) {

    route("/cart") {
        get("/{userId}") {
            val userId = call.parameters["userId"]?.toIntOrNull()
            if (userId == null) {
                call.respond(HttpStatusCode.BadRequest, "Invalid user ID")
                return@get
            }

            var cart = cartRepository.getCartByUserId(userId)
            if (cart == null) {
                cart = cartRepository.createCart(userId)
            }
            call.respond(cart)
        }

        post("/{userId}/items") {
            val userId = call.parameters["userId"]?.toIntOrNull()
            if (userId == null) {
                call.respond(HttpStatusCode.BadRequest, "Invalid user ID")
                return@post
            }

            val formParameters = call.receiveParameters()
            val productId = formParameters["productId"]?.toIntOrNull()
            val quantity = formParameters["quantity"]?.toIntOrNull()

            if (productId == null || quantity == null) {
                call.respond(HttpStatusCode.BadRequest, "Invalid product ID or quantity")
                return@post
            }

            var cart = cartRepository.getCartByUserId(userId)
            if (cart == null) {
                cart = cartRepository.createCart(userId)
            }

            cartRepository.addOrUpdateItem(cart.id, productId, quantity)
            val updatedCart = cartRepository.getCartByUserId(userId)
            call.respond(updatedCart!!)
        }

        delete("/{userId}/items/{productId}") {
            val userId = call.parameters["userId"]?.toIntOrNull()
            val productId = call.parameters["productId"]?.toIntOrNull()

            if (userId == null || productId == null) {
                call.respond(HttpStatusCode.BadRequest, "Invalid user ID or product ID")
                return@delete
            }

            val cart = cartRepository.getCartByUserId(userId)
            if (cart == null) {
                call.respond(HttpStatusCode.NotFound, "Cart not found")
                return@delete
            }

            cartRepository.removeItem(cart.id, productId)
            val updatedCart = cartRepository.getCartByUserId(userId)
            call.respond(updatedCart!!)
        }

        delete("/{userId}") {
            val userId = call.parameters["userId"]?.toIntOrNull()
            if (userId == null) {
                call.respond(HttpStatusCode.BadRequest, "Invalid user ID")
                return@delete
            }

            val cart = cartRepository.getCartByUserId(userId)
            if (cart == null) {
                call.respond(HttpStatusCode.NotFound, "Cart not found")
                return@delete
            }

            cartRepository.clearCart(cart.id)
            val updatedCart = cartRepository.getCartByUserId(userId)
            call.respond(updatedCart!!)
        }
    }
}