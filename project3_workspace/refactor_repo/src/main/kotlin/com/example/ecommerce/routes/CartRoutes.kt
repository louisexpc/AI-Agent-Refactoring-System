package com.example.ecommerce.routes

import com.example.ecommerce.controller.cartRouting
import io.ktor.server.routing.*

fun Routing.cartRoutes() {
    cartRouting()
}
