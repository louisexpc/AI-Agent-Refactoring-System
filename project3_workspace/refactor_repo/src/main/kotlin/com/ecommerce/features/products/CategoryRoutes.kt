package com.ecommerce.features.products

import com.ecommerce.features.products.models.CreateCategoryRequest
import com.ecommerce.features.products.models.UpdateCategoryRequest
import io.ktor.http.*
import io.ktor.server.application.*
import io.ktor.server.request.*
import io.ktor.server.response.*
import io.ktor.server.routing.*

fun Route.categoryRoutes(categoryService: CategoryService) {
    route("/categories") {
        post {
            val request = call.receive<CreateCategoryRequest>()
            val category = categoryService.createCategory(request)
            call.respond(HttpStatusCode.Created, category)
        }

        get {
            val categories = categoryService.getAllCategories()
            call.respond(categories)
        }

        get("/{id}") {
            val id = call.parameters["id"]?.toIntOrNull()
            if (id == null) {
                call.respond(HttpStatusCode.BadRequest, "Invalid category ID")
                return@get
            }
            val category = categoryService.getCategoryById(id)
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
            val request = call.receive<UpdateCategoryRequest>()
            val updatedCategory = categoryService.updateCategory(id, request)
            if (updatedCategory != null) {
                call.respond(updatedCategory)
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
            val deleted = categoryService.deleteCategory(id)
            if (deleted) {
                call.respond(HttpStatusCode.OK, "Category deleted")
            } else {
                call.respond(HttpStatusCode.NotFound, "Category not found")
            }
        }
    }
}
