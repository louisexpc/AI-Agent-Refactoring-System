
package com.ecommerce.features.auth

import com.ecommerce.features.auth.models.UserProfileUpdateRequest
import io.ktor.server.application.*
import io.ktor.server.auth.*
import io.ktor.server.auth.jwt.*
import io.ktor.server.request.*
import io.ktor.server.response.*
import io.ktor.server.routing.*

fun Route.userRoutes(userService: UserService) {

    authenticate("auth-jwt") {
        get("/{id}") {
            val id = call.parameters["id"]?.toIntOrNull()
            val principal = call.principal<JWTPrincipal>()
            val userId = principal?.payload?.getClaim("userId")?.asInt()

            if (id != null && id == userId) {
                val user = userService.getUserProfile(id)
                if (user != null) {
                    call.respond(user) // Consider creating a UserProfileResponse
                } else {
                    call.respond(io.ktor.http.HttpStatusCode.NotFound)
                }
            } else {
                call.respond(io.ktor.http.HttpStatusCode.Forbidden)
            }
        }

        put("/{id}") {
            val id = call.parameters["id"]?.toIntOrNull()
            val principal = call.principal<JWTPrincipal>()
            val userId = principal?.payload?.getClaim("userId")?.asInt()
            val request = call.receive<UserProfileUpdateRequest>()

            if (id != null && id == userId) {
                val updatedUser = userService.updateUserProfile(id, request)
                if (updatedUser != null) {
                    call.respond(updatedUser) // Consider creating a UserProfileResponse
                } else {
                    call.respond(io.ktor.http.HttpStatusCode.NotFound)
                }
            } else {
                call.respond(io.ktor.http.HttpStatusCode.Forbidden)
            }
        }

        delete("/{id}") {
            val id = call.parameters["id"]?.toIntOrNull()
            val principal = call.principal<JWTPrincipal>()
            val userId = principal?.payload?.getClaim("userId")?.asInt()

            if (id != null && id == userId) {
                userService.deleteUser(id)
                call.respond(io.ktor.http.HttpStatusCode.OK)
            } else {
                call.respond(io.ktor.http.HttpStatusCode.Forbidden)
            }
        }
    }
}
