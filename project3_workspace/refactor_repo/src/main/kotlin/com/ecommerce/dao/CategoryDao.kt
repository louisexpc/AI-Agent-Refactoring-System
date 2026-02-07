package com.ecommerce.dao

import com.ecommerce.models.Category
import java.sql.Connection
import java.sql.Statement

class CategoryDao(private val connection: Connection) {

    fun createTable() {
        val query = """
            CREATE TABLE IF NOT EXISTS categories (
                id SERIAL PRIMARY KEY,
                title VARCHAR(255) UNIQUE NOT NULL,
                createdAt TIMESTAMP NOT NULL,
                updatedAt TIMESTAMP NOT NULL
            )
            """
        connection.createStatement().use { it.execute(query) }
    }

    fun create(category: Category): Category {
        val query = "INSERT INTO categories (title, createdAt, updatedAt) VALUES (?, ?, ?)"
        val preparedStatement = connection.prepareStatement(query, Statement.RETURN_GENERATED_KEYS)
        preparedStatement.setString(1, category.title)
        preparedStatement.setTimestamp(2, java.sql.Timestamp.valueOf(category.createdAt))
        preparedStatement.setTimestamp(3, java.sql.Timestamp.valueOf(category.updatedAt))
        preparedStatement.executeUpdate()
        val generatedKeys = preparedStatement.resultSet
        if (generatedKeys.next()) {
            return category.copy(id = generatedKeys.getInt(1))
        }
        throw Exception("Failed to create category")
    }

    fun findById(id: Int): Category? {
        val query = "SELECT * FROM categories WHERE id = ?"
        val preparedStatement = connection.prepareStatement(query)
        preparedStatement.setInt(1, id)
        val resultSet = preparedStatement.executeQuery()
        return if (resultSet.next()) {
            Category(
                id = resultSet.getInt("id"),
                title = resultSet.getString("title"),
                createdAt = resultSet.getTimestamp("createdAt").toLocalDateTime(),
                updatedAt = resultSet.getTimestamp("updatedAt").toLocalDateTime()
            )
        } else {
            null
        }
    }

    fun findAll(): List<Category> {
        val query = "SELECT * FROM categories"
        val statement = connection.createStatement()
        val resultSet = statement.executeQuery(query)
        val categories = mutableListOf<Category>()
        while (resultSet.next()) {
            categories.add(
                Category(
                    id = resultSet.getInt("id"),
                    title = resultSet.getString("title"),
                    createdAt = resultSet.getTimestamp("createdAt").toLocalDateTime(),
                    updatedAt = resultSet.getTimestamp("updatedAt").toLocalDateTime()
                )
            )
        }
        return categories
    }

    fun update(category: Category) {
        val query = "UPDATE categories SET title = ?, updatedAt = ? WHERE id = ?"
        val preparedStatement = connection.prepareStatement(query)
        preparedStatement.setString(1, category.title)
        preparedStatement.setTimestamp(2, java.sql.Timestamp.valueOf(category.updatedAt))
        preparedStatement.setInt(3, category.id)
        preparedStatement.executeUpdate()
    }

    fun delete(id: Int) {
        val query = "DELETE FROM categories WHERE id = ?"
        val preparedStatement = connection.prepareStatement(query)
        preparedStatement.setInt(1, id)
        preparedStatement.executeUpdate()
    }
}
