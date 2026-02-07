package com.ecommerce.features.products

import com.ecommerce.features.products.models.CreateProductRequest
import com.ecommerce.features.products.models.UpdateProductRequest
import io.ktor.http.*
import io.ktor.server.application.*
import io.ktor.server.request.*
import io.ktor.server.response.*
import io.ktor.server.routing.*

fun Route.productRoutes(productService: ProductService) {
    route("/products") {
        post {
            val request = call.receive<CreateProductRequest>()
            val product = productService.createProduct(request)
            call.respond(HttpStatusCode.Created, product)
        }

        get {
            val products = productService.getAllProducts()
            call.respond(products)
        }

        get("/{id}") {
            val id = call.parameters["id"]?.toIntOrNull()
            if (id == null) {
                call.respond(HttpStatusCode.BadRequest, "Invalid product ID")
                return@get
            }
            val product = productService.getProductById(id)
            if (product != null) {
                call.respond(product)
            } else {
                call.respond(HttpStatusCode.NotFound, "Product not found")
            }
        }

        put("/{id}") {
            val id = call.parameters["id"]?.toIntOrNull()
            if (id == null) {
                call.respond(HttpStatusCode.BadRequest, "Invalid product ID")
                return@put
            }
            val request = call.receive<UpdateProductRequest>()
            val updatedProduct = productService.updateProduct(id, request)
            if (updatedProduct != null) {
                call.respond(updatedProduct)
            } else {
                call.respond(HttpStatusCode.NotFound, "Product not found")
            }
        }

        delete("/{id}") {
            val id = call.parameters["id"]?.toIntOrNull()
            if (id == null) {
                call.respond(HttpStatusCode.BadRequest, "Invalid product ID")
                return@delete
            }
            val deleted = productService.deleteProduct(id)
            if (deleted) {
                call.respond(HttpStatusCode.OK, "Product deleted")
            } else {
                call.respond(HttpStatusCode.NotFound, "Product not found")
            }
        }
    }
}
