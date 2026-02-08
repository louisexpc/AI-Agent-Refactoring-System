package com.ecommerce.controllers

import com.ecommerce.dao.BlogDao
import com.ecommerce.models.Blog
import io.ktor.http.*
import io.ktor.server.application.* 
import io.ktor.server.request.* 
import io.ktor.server.response.*

class BlogController(private val blogDao: BlogDao) {

    suspend fun createBlog(call: ApplicationCall) {
        val parameters = call.receive<Parameters>()
        val title = parameters["title"] ?: return call.respond(HttpStatusCode.BadRequest, "Missing title")
        val content = parameters["content"] ?: return call.respond(HttpStatusCode.BadRequest, "Missing content")
        val category = parameters["category"] ?: return call.respond(HttpStatusCode.BadRequest, "Missing category")
        val image = parameters["image"]
        val author = parameters["author"]

        val blog = blogDao.createBlog(title, content, category, image, author)
        if (blog != null) {
            call.respond(HttpStatusCode.Created, blog)
        } else {
            call.respond(HttpStatusCode.InternalServerError, "Failed to create blog")
        }
    }

    suspend fun getAllBlogs(call: ApplicationCall) {
        val blogs = blogDao.getAllBlogs()
        call.respond(HttpStatusCode.OK, blogs)
    }

    suspend fun getBlog(call: ApplicationCall) {
        val id = call.parameters["id"]?.toIntOrNull() ?: return call.respond(HttpStatusCode.BadRequest, "Invalid blog ID")
        val blog = blogDao.getBlog(id)
        if (blog != null) {
            call.respond(HttpStatusCode.OK, blog)
        } else {
            call.respond(HttpStatusCode.NotFound, "Blog not found")
        }
    }

    suspend fun updateBlog(call: ApplicationCall) {
        val id = call.parameters["id"]?.toIntOrNull() ?: return call.respond(HttpStatusCode.BadRequest, "Invalid blog ID")
        val parameters = call.receive<Parameters>()
        val title = parameters["title"]
        val content = parameters["content"]
        val category = parameters["category"]

        val success = blogDao.updateBlog(id, title, content, category)
        if (success) {
            call.respond(HttpStatusCode.OK, "Blog updated successfully")
        } else {
            call.respond(HttpStatusCode.InternalServerError, "Failed to update blog")
        }
    }

    suspend fun deleteBlog(call: ApplicationCall) {
        val id = call.parameters["id"]?.toIntOrNull() ?: return call.respond(HttpStatusCode.BadRequest, "Invalid blog ID")
        val success = blogDao.deleteBlog(id)
        if (success) {
            call.respond(HttpStatusCode.OK, "Blog deleted successfully")
        } else {
            call.respond(HttpStatusCode.NotFound, "Blog not found")
        }
    }

    suspend fun likeBlog(call: ApplicationCall) {
        val id = call.parameters["blogId"]?.toIntOrNull() ?: return call.respond(HttpStatusCode.BadRequest, "Invalid blog ID")
        val userId = 1 // Replace with actual user ID from authentication
        val success = blogDao.likeBlog(id, userId)
        if (success) {
            call.respond(HttpStatusCode.OK, "Blog liked successfully")
        } else {
            call.respond(HttpStatusCode.InternalServerError, "Failed to like blog")
        }
    }

    suspend fun unlikeBlog(call: ApplicationCall) {
        val id = call.parameters["blogId"]?.toIntOrNull() ?: return call.respond(HttpStatusCode.BadRequest, "Invalid blog ID")
        val userId = 1 // Replace with actual user ID from authentication
        val success = blogDao.unlikeBlog(id, userId)
        if (success) {
            call.respond(HttpStatusCode.OK, "Blog unliked successfully")
        } else {
            call.respond(HttpStatusCode.InternalServerError, "Failed to unlike blog")
        }
    }
}
