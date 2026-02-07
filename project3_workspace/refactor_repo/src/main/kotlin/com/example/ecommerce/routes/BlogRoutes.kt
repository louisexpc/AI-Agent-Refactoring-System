package com.example.ecommerce.routes

import com.example.ecommerce.controller.BlogController
import org.springframework.context.annotation.Bean
import org.springframework.context.annotation.Configuration
import org.springframework.web.reactive.function.server.router

/**
 * Defines the routes for the Blog API.
 * NOTE: This uses Spring WebFlux `router` which may conflict with the
 * Spring MVC `@RestController` used in `BlogController`.
 * This pattern is followed for consistency with other `*Routes.kt` files.
 */
@Configuration
class BlogRoutes(private val blogController: BlogController) {

    @Bean
    fun blogRoutes() = router {
        "/api/blogs".nest {
            // These routes are already defined by @RequestMapping in BlogController.
            // This file is created to follow the pattern of other *Routes.kt files.
        }
    }
}
