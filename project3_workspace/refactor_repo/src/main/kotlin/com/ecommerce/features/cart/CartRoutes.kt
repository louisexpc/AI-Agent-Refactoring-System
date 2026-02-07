package com.ecommerce.features.cart

import com.ecommerce.features.cart.models.AddToCartRequest
import com.ecommerce.features.cart.models.UpdateCartItemRequest
import io.ktor.http.* 
import io.ktor.server.application.*
import io.ktor.server.request.*
import io.ktor.server.response.* 
import io.ktor.server.routing.* 

fun Route.cartRoutes(cartService: CartService) {

    route("/cart") {
        get("/{userId}") { 
            val userId = call.parameters["userId"]?.toIntOrNull() ?: return@get call.respond(HttpStatusCode.BadRequest)
            val cart = cartService.getCart(userId)
            if (cart != null) {
                call.respond(cart)
            } else {
                call.respond(HttpStatusCode.NotFound)
            }
        }

        post("/{userId}/items") { 
            val userId = call.parameters["userId"]?.toIntOrNull() ?: return@post call.respond(HttpStatusCode.BadRequest)
            val request = call.receive<AddToCartRequest>()
            cartService.addItemToCart(userId, request.productId, request.quantity)
            call.respond(HttpStatusCode.Created)
        }

        put("/{userId}/items/{productId}") { 
            val userId = call.parameters["userId"]?.toIntOrNull() ?: return@put call.respond(HttpStatusCode.BadRequest)
            val productId = call.parameters["productId"]?.toIntOrNull() ?: return@put call.respond(HttpStatusCode.BadRequest)
            val request = call.receive<UpdateCartItemRequest>()
            cartService.updateCartItem(userId, productId, request.quantity)
            call.respond(HttpStatusCode.OK)
        }

        delete("/{userId}/items/{productId}") { 
            val userId = call.parameters["userId"]?.toIntOrNull() ?: return@delete call.respond(HttpStatusCode.BadRequest)
            val productId = call.parameters["productId"]?.toIntOrNull() ?: return@delete call.respond(HttpStatusCode.BadRequest)
            cartService.removeItemFromCart(userId, productId)
            call.respond(HttpStatusCode.NoContent)
        }

        delete("/{userId}") { 
            val userId = call.parameters["userId"]?.toIntOrNull() ?: return@delete call.respond(HttpStatusCode.BadRequest)
            cartService.clearCart(userId)
            call.respond(HttpStatusCode.NoContent)
        }
    }
}
