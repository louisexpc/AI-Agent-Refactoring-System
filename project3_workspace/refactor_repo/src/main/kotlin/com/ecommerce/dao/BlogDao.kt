package com.ecommerce.dao

import com.ecommerce.models.Blog

interface BlogDao {
    suspend fun createBlog(title: String, content: String, category: String, image: String?, author: String?): Blog?
    suspend fun getAllBlogs(): List<Blog>
    suspend fun getBlog(id: Int): Blog?
    suspend fun updateBlog(id: Int, title: String?, content: String?, category: String?): Boolean
    suspend fun deleteBlog(id: Int): Boolean
    suspend fun likeBlog(id: Int, userId: Int): Boolean
    suspend fun unlikeBlog(id: Int, userId: Int): Boolean
}
