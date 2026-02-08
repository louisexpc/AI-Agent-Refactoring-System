package com.example.ecommerce.service

import com.example.ecommerce.model.Blog
import org.springframework.stereotype.Service

@Service
class BlogServiceImpl : BlogService {
    private val blogs = mutableListOf<Blog>()

    override fun getAllBlogs(): List<Blog> {
        return blogs
    }

    override fun getBlogById(id: Long): Blog? {
        return blogs.find { it.id == id }
    }

    override fun createBlog(blog: Blog): Blog {
        val newBlog = blog.copy(id = (blogs.size + 1).toLong())
        blogs.add(newBlog)
        return newBlog
    }

    override fun updateBlog(id: Long, blog: Blog): Blog? {
        val index = blogs.indexOfFirst { it.id == id }
        if (index != -1) {
            val updatedBlog = blog.copy(id = id)
            blogs[index] = updatedBlog
            return updatedBlog
        }
        return null
    }

    override fun deleteBlog(id: Long): Boolean {
        return blogs.removeIf { it.id == id }
    }
}
