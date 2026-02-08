package com.example.ecommerce.routes

import com.example.ecommerce.controller.ProductController
import org.springframework.context.annotation.Bean
import org.springframework.context.annotation.Configuration
import org.springframework.web.reactive.function.server.router

@Configuration
class ProductRoutes(private val productController: ProductController) {

    @Bean
    fun productRoutes() = router {
        "/api/products".nest {
            GET("/", productController::getAllProducts)
            GET("/{id}", productController::getProductById)
            POST("/", productController::createProduct)
            PUT("/{id}", productController::updateProduct)
            DELETE("/{id}", productController::deleteProduct)
        }
    }
}
