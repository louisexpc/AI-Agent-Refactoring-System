package com.example.ecommerce.routes

import com.example.ecommerce.controller.UserController
import org.springframework.context.annotation.Bean
import org.springframework.context.annotation.Configuration
import org.springframework.web.reactive.function.server.router

@Configuration
class UserRoutes(private val userController: UserController) {

    @Bean
    fun userRoutes() = router {
        "/api/users".nest {
            GET("/", userController::getAllUsers)
            GET("/{id}", userController::getUserById)
            POST("/", userController::createUser)
            PUT("/{id}", userController::updateUser)
            DELETE("/{id}", userController::deleteUser)
        }
    }
}
