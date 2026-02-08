package com.ecommerce.controllers

import com.ecommerce.dao.CartDao
import com.ecommerce.models.CartItem
import io.ktor.http.* 
import io.ktor.server.application.*
import io.ktor.server.request.*
import io.ktor.server.response.*
import io.ktor.server.routing.*

fun Route.cartRouting(cartDao: CartDao) {
    route("/cart") {
        post("/add") {
            val item = call.receive<CartItem>()
            val userId = 1 // TODO: Get user from authentication
            var cart = cartDao.getCart(userId)
            if (cart == null) {
                cart = cartDao.create(userId)
            }
            cartDao.addItem(cart.id, item.productId, item.quantity)
            call.respond(HttpStatusCode.Created, "Item added to cart")
        }

        get {
            val userId = 1 // TODO: Get user from authentication
            val cart = cartDao.getCart(userId)
            if (cart != null) {
                call.respond(cart)
            } else {
                call.respond(HttpStatusCode.NotFound, "Cart not found")
            }
        }

        get("/cart-total") {
            // Implementation for calculating cart total
            call.respond(HttpStatusCode.OK, "Cart total calculated")
        }

        get("/empty-cart") {
            val userId = 1 // TODO: Get user from authentication
            val cart = cartDao.getCart(userId)
            if (cart != null) {
                cartDao.clear(cart.id)
                call.respond(HttpStatusCode.OK, "Cart emptied")
            } else {
                call.respond(HttpStatusCode.NotFound, "Cart not found")
            }
        }

        post("/apply-coupon") {
            // Implementation for applying coupon
            call.respond(HttpStatusCode.OK, "Coupon applied")
        }
    }
}