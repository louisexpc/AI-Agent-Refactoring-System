package com.example.ecommerce.service

import com.example.ecommerce.model.Blog

interface BlogService {
    fun getAllBlogs(): List<Blog>
    fun getBlogById(id: Long): Blog?
    fun createBlog(blog: Blog): Blog
    fun updateBlog(id: Long, blog: Blog): Blog?
    fun deleteBlog(id: Long): Boolean
}
