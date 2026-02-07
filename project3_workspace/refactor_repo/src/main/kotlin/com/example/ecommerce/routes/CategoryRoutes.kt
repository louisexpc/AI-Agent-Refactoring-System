package com.example.ecommerce.routes

import com.example.ecommerce.controller.CategoryController
import org.springframework.context.annotation.Bean
import org.springframework.context.annotation.Configuration
import org.springframework.web.reactive.function.server.router

@Configuration
class CategoryRoutes(private val categoryController: CategoryController) {

    @Bean
    fun categoryRoutes() = router {
        "/api/categories".nest {
            GET("/", categoryController::getAllCategories)
            GET("/{id}", categoryController::getCategoryById)
            POST("/", categoryController::createCategory)
            PUT("/{id}", categoryController::updateCategory)
            DELETE("/{id}", categoryController::deleteCategory)
        }
    }
}
