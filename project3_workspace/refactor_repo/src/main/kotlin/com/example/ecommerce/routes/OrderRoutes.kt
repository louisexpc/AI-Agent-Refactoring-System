package com.example.ecommerce.routes

import com.example.ecommerce.controller.orderRouting
import io.ktor.server.routing.*

fun Routing.orderRoutes() {
    orderRouting()
}
