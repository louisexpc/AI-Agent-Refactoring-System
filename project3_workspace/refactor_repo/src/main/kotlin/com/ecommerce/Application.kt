
package com.ecommerce

import com.ecommerce.plugins.configureRouting
import com.ecommerce.plugins.configureSerialization
import com.ecommerce.plugins.Database
import io.ktor.server.application.*
import io.ktor.server.cio.*
import io.ktor.server.engine.*

fun main() {
    embeddedServer(CIO, port = 8080, host = "0.0.0.0", module = Application::module)
        .start(wait = true)
}

fun Application.module() {
    Database.init(this)
    configureSerialization()
    configureRouting()
}
