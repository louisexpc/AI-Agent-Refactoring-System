package com.ecommerce.routes

import com.ecommerce.models.Blog
import com.ecommerce.repository.BlogRepository
import io.ktor.server.application.*
import io.ktor.server.request.*
import io.ktor.server.response.*
import io.ktor.server.routing.*

fun Route.blogRoutes(blogRepository: BlogRepository) {
    route("/api/blog") {
        post {
            val blog = call.receive<Blog>()
            val createdBlog = blogRepository.createBlog(blog)
            call.respond(createdBlog)
        }

        put("/likes") {
            val params = call.receive<Map<String, Int>>()
            val blogId = params["blogId"]!!
            val userId = params["userId"]!! // Assuming you have user authentication
            val updatedBlog = blogRepository.likeBlog(blogId, userId)
            call.respond(updatedBlog!!)
        }

        put("/dislikes") {
            val params = call.receive<Map<String, Int>>()
            val blogId = params["blogId"]!!
            val userId = params["userId"]!! // Assuming you have user authentication
            val updatedBlog = blogRepository.dislikeBlog(blogId, userId)
            call.respond(updatedBlog!!)
        }

        get("/{id}") {
            val id = call.parameters["id"]?.toIntOrNull()
            if (id != null) {
                val blog = blogRepository.getBlogById(id)
                if (blog != null) {
                    call.respond(blog)
                } else {
                    call.respondText("Blog not found", status = io.ktor.http.HttpStatusCode.NotFound)
                }
            } else {
                call.respondText("Invalid ID", status = io.ktor.http.HttpStatusCode.BadRequest)
            }
        }

        get {
            val blogs = blogRepository.getAllBlogs()
            call.respond(blogs)
        }

        put("/{id}") {
            val id = call.parameters["id"]?.toIntOrNull()
            val blog = call.receive<Blog>()
            if (id != null) {
                val updatedBlog = blogRepository.updateBlog(id, blog)
                if (updatedBlog != null) {
                    call.respond(updatedBlog)
                } else {
                    call.respondText("Blog not found", status = io.ktor.http.HttpStatusCode.NotFound)
                }
            } else {
                call.respondText("Invalid ID", status = io.ktor.http.HttpStatusCode.BadRequest)
            }
        }

        delete("/{id}") {
            val id = call.parameters["id"]?.toIntOrNull()
            if (id != null) {
                if (blogRepository.deleteBlog(id)) {
                    call.respondText("Blog deleted successfully")
                } else {
                    call.respondText("Blog not found", status = io.ktor.http.HttpStatusCode.NotFound)
                }
            } else {
                call.respondText("Invalid ID", status = io.ktor.http.HttpStatusCode.BadRequest)
            }
        }
    }
}
