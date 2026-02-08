package com.example.ecommerce.controller

import com.example.ecommerce.model.Blog
import com.example.ecommerce.service.BlogService
import org.springframework.http.ResponseEntity
import org.springframework.web.bind.annotation.*

@RestController
@RequestMapping("/api/blogs")
class BlogController(private val blogService: BlogService) {

    @GetMapping
    fun getAllBlogs(): ResponseEntity<List<Blog>> {
        return ResponseEntity.ok(blogService.getAllBlogs())
    }

    @GetMapping("/{id}")
    fun getBlogById(@PathVariable id: Long): ResponseEntity<Blog> {
        return blogService.getBlogById(id)
            ?.let { ResponseEntity.ok(it) }
            ?: ResponseEntity.notFound().build()
    }

    @PostMapping
    fun createBlog(@RequestBody blog: Blog): ResponseEntity<Blog> {
        return ResponseEntity.ok(blogService.createBlog(blog))
    }

    @PutMapping("/{id}")
    fun updateBlog(@PathVariable id: Long, @RequestBody blog: Blog): ResponseEntity<Blog> {
        return blogService.updateBlog(id, blog)
            ?.let { ResponseEntity.ok(it) }
            ?: ResponseEntity.notFound().build()
    }

    @DeleteMapping("/{id}")
    fun deleteBlog(@PathVariable id: Long): ResponseEntity<Unit> {
        return if (blogService.deleteBlog(id)) {
            ResponseEntity.noContent().build()
        } else {
            ResponseEntity.notFound().build()
        }
    }
}
