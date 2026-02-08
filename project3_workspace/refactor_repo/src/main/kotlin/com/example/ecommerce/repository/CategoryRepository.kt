package com.example.ecommerce.repository

import com.example.ecommerce.model.Category

class CategoryRepository {

    fun save(category: Category): Category {
        //language=SQL
        val sql = "INSERT INTO categories (title) VALUES (?)"
        // Execute SQL
        return category
    }

    fun findById(id: Long): Category? {
        //language=SQL
        val sql = "SELECT * FROM categories WHERE id = ?"
        // Execute SQL
        return null
    }

    fun findAll(): List<Category> {
        //language=SQL
        val sql = "SELECT * FROM categories"
        // Execute SQL
        return emptyList()
    }

    fun update(category: Category): Category {
        //language=SQL
        val sql = "UPDATE categories SET title = ? WHERE id = ?"
        // Execute SQL
        return category
    }

    fun deleteById(id: Long) {
        //language=SQL
        val sql = "DELETE FROM categories WHERE id = ?"
        // Execute SQL
    }
}
