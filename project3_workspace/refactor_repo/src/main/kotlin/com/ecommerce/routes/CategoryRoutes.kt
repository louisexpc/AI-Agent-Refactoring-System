package com.ecommerce.routes

import com.ecommerce.repository.Category
import com.ecommerce.repository.CategoryRepository
import io.ktor.http.*
import io.ktor.server.application.*
import io.ktor.server.request.*
import io.ktor.server.response.*
import io.ktor.server.routing.*

fun Route.categoryRoutes(categoryRepository: CategoryRepository) {

    route("/categories") {
        post("/create") {
            val category = call.receive<Category>()
            val createdCategory = categoryRepository.createCategory(category)
            call.respond(HttpStatusCode.Created, createdCategory)
        }

        get("/all") {
            val categories = categoryRepository.getAllCategories()
            call.respond(categories)
        }

        get("/{id}") {
            val id = call.parameters["id"]?.toIntOrNull()
            if (id == null) {
                call.respond(HttpStatusCode.BadRequest, "Invalid category ID")
                return@get
            }
            val category = categoryRepository.getCategoryById(id)
            if (category != null) {
                call.respond(category)
            } else {
                call.respond(HttpStatusCode.NotFound, "Category not found")
            }
        }

        put("/{id}") {
            val id = call.parameters["id"]?.toIntOrNull()
            if (id == null) {
                call.respond(HttpStatusCode.BadRequest, "Invalid category ID")
                return@put
            }
            val category = call.receive<Category>()
            val updated = categoryRepository.updateCategory(id, category)
            if (updated) {
                call.respond(HttpStatusCode.OK, "Category updated successfully")
            } else {
                call.respond(HttpStatusCode.NotFound, "Category not found")
            }
        }

        delete("/{id}") {
            val id = call.parameters["id"]?.toIntOrNull()
            if (id == null) {
                call.respond(HttpStatusCode.BadRequest, "Invalid category ID")
                return@delete
            }
            val deleted = categoryRepository.deleteCategory(id)
            if (deleted) {
                call.respond(HttpStatusCode.OK, "Category deleted successfully")
            } else {
                call.respond(HttpStatusCode.NotFound, "Category not found")
            }
        }
    }
}
