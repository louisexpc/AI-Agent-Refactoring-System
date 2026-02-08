package com.ecommerce.routes

import com.ecommerce.repository.Product
import com.ecommerce.repository.ProductRepository
import io.ktor.http.*
import io.ktor.server.application.*
import io.ktor.server.request.*
import io.ktor.server.response.*
import io.ktor.server.routing.*

fun Route.productRoutes(productRepository: ProductRepository) {

    route("/products") {
        post("/create") {
            val product = call.receive<Product>()
            val createdProduct = productRepository.createProduct(product)
            call.respond(HttpStatusCode.Created, createdProduct)
        }

        get("/all") {
            val products = productRepository.getAllProducts()
            call.respond(products)
        }

        get("/{id}") {
            val id = call.parameters["id"]?.toIntOrNull()
            if (id == null) {
                call.respond(HttpStatusCode.BadRequest, "Invalid product ID")
                return@get
            }
            val product = productRepository.getProductById(id)
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
            val product = call.receive<Product>()
            val updated = productRepository.updateProduct(id, product)
            if (updated) {
                call.respond(HttpStatusCode.OK, "Product updated successfully")
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
            val deleted = productRepository.deleteProduct(id)
            if (deleted) {
                call.respond(HttpStatusCode.OK, "Product deleted successfully")
            } else {
                call.respond(HttpStatusCode.NotFound, "Product not found")
            }
        }

        post("/{id}/upload") {
            val id = call.parameters["id"]?.toIntOrNull()
            if (id == null) {
                call.respond(HttpStatusCode.BadRequest, "Invalid product ID")
                return@post
            }
            // This is a simplified version of image upload.
            // In a real application, you would handle multipart file uploads.
            val imageUrl = call.receive<String>()
            val productImage = productRepository.addImageToProduct(id, imageUrl)
            call.respond(HttpStatusCode.Created, productImage)
        }
    }
}
