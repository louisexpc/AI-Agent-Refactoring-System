package com.example.ecommerce.repository

import com.example.ecommerce.model.Blog

class BlogRepository {

    fun save(blog: Blog): Blog {
        //language=SQL
        val sql = "INSERT INTO blogs (title, description, category, num_views, is_liked, is_disliked, image, author) VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
        // Execute SQL
        return blog
    }

    fun findById(id: Long): Blog? {
        //language=SQL
        val sql = "SELECT * FROM blogs WHERE id = ?"
        // Execute SQL
        return null
    }

    fun findAll(): List<Blog> {
        //language=SQL
        val sql = "SELECT * FROM blogs"
        // Execute SQL
        return emptyList()
    }

    fun update(blog: Blog): Blog {
        //language=SQL
        val sql = "UPDATE blogs SET title = ?, description = ?, category = ?, num_views = ?, is_liked = ?, is_disliked = ?, image = ?, author = ? WHERE id = ?"
        // Execute SQL
        return blog
    }

    fun deleteById(id: Long) {
        //language=SQL
        val sql = "DELETE FROM blogs WHERE id = ?"
        // Execute SQL
    }
}
