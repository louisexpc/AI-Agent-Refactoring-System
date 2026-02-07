
package com.ecommerce.features.auth

import com.ecommerce.features.auth.models.UserLoginRequest
import com.ecommerce.features.auth.models.UserLoginResponse
import com.ecommerce.features.auth.models.UserRegistrationRequest
import io.ktor.server.application.*
import io.ktor.server.request.*
import io.ktor.server.response.*
import io.ktor.server.routing.*

fun Route.authRoutes(authService: AuthService) {

    post("/register") {
        val request = call.receive<UserRegistrationRequest>()
        val user = authService.registerUser(request)
        call.respond(user) // Consider creating a UserResponse object
    }

    post("/login") {
        val request = call.receive<UserLoginRequest>()
        val token = authService.login(request)
        if (token != null) {
            call.respond(UserLoginResponse(accessToken = token, refreshToken = "")) // Dummy refresh token
        } else {
            call.respond(io.ktor.http.HttpStatusCode.Unauthorized, "Invalid credentials")
        }
    }
}
