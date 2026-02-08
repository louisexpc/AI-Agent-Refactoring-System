package com.ecommerce.repository

import java.sql.Connection
import java.sql.Statement

data class Category(
    var id: Int? = null,
    val name: String,
    val description: String
)

class CategoryRepository(private val connection: Connection) {

    fun createCategory(category: Category): Category {
        val sql = "INSERT INTO categories (name, description) VALUES (?, ?)"
        val statement = connection.prepareStatement(sql, Statement.RETURN_GENERATED_KEYS)
        statement.setString(1, category.name)
        statement.setString(2, category.description)
        statement.executeUpdate()

        val generatedKeys = statement.generatedKeys
        if (generatedKeys.next()) {
            category.id = generatedKeys.getInt(1)
        }
        return category
    }

    fun getAllCategories(): List<Category> {
        val categories = mutableListOf<Category>()
        val sql = "SELECT * FROM categories"
        val statement = connection.prepareStatement(sql)
        val resultSet = statement.executeQuery()

        while (resultSet.next()) {
            categories.add(
                Category(
                    id = resultSet.getInt("id"),
                    name = resultSet.getString("name"),
                    description = resultSet.getString("description")
                )
            )
        }
        return categories
    }

    fun getCategoryById(id: Int): Category? {
        val sql = "SELECT * FROM categories WHERE id = ?"
        val statement = connection.prepareStatement(sql)
        statement.setInt(1, id)
        val resultSet = statement.executeQuery()

        return if (resultSet.next()) {
            Category(
                id = resultSet.getInt("id"),
                name = resultSet.getString("name"),
                description = resultSet.getString("description")
            )
        } else {
            null
        }
    }

    fun updateCategory(id: Int, category: Category): Boolean {
        val sql = "UPDATE categories SET name = ?, description = ? WHERE id = ?"
        val statement = connection.prepareStatement(sql)
        statement.setString(1, category.name)
        statement.setString(2, category.description)
        statement.setInt(3, id)
        return statement.executeUpdate() > 0
    }

    fun deleteCategory(id: Int): Boolean {
        val sql = "DELETE FROM categories WHERE id = ?"
        val statement = connection.prepareStatement(sql)
        statement.setInt(1, id)
        return statement.executeUpdate() > 0
    }
}
