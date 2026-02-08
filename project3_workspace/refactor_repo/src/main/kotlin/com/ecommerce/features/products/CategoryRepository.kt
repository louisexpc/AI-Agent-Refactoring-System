package com.ecommerce.features.products

import com.ecommerce.features.products.models.Category
import com.ecommerce.features.products.models.CreateCategoryRequest
import com.ecommerce.features.products.models.UpdateCategoryRequest
import java.sql.Connection
import java.sql.Statement

class CategoryRepository(private val connection: Connection) {

    fun createCategory(request: CreateCategoryRequest): Category {
        val sql = "INSERT INTO categories (title) VALUES (?)"
        val preparedStatement = connection.prepareStatement(sql, Statement.RETURN_GENERATED_KEYS)
        preparedStatement.setString(1, request.title)
        preparedStatement.executeUpdate()
        val generatedKeys = preparedStatement.generatedKeys
        generatedKeys.next()
        val id = generatedKeys.getInt(1)
        return findCategoryById(id)!!
    }

    fun findAllCategories(): List<Category> {
        val sql = "SELECT * FROM categories"
        val statement = connection.createStatement()
        val resultSet = statement.executeQuery(sql)
        val categories = mutableListOf<Category>()
        while (resultSet.next()) {
            categories.add(
                Category(
                    id = resultSet.getInt("id"),
                    title = resultSet.getString("title"),
                    createdAt = resultSet.getTimestamp("created_at").toLocalDateTime(),
                    updatedAt = resultSet.getTimestamp("updated_at").toLocalDateTime()
                )
            )
        }
        return categories
    }

    fun findCategoryById(id: Int): Category? {
        val sql = "SELECT * FROM categories WHERE id = ?"
        val preparedStatement = connection.prepareStatement(sql)
        preparedStatement.setInt(1, id)
        val resultSet = preparedStatement.executeQuery()
        return if (resultSet.next()) {
            Category(
                id = resultSet.getInt("id"),
                title = resultSet.getString("title"),
                createdAt = resultSet.getTimestamp("created_at").toLocalDateTime(),
                updatedAt = resultSet.getTimestamp("updated_at").toLocalDateTime()
            )
        } else {
            null
        }
    }

    fun updateCategory(id: Int, request: UpdateCategoryRequest): Category? {
        val sql = "UPDATE categories SET title = ? WHERE id = ?"
        val preparedStatement = connection.prepareStatement(sql)
        preparedStatement.setString(1, request.title)
        preparedStatement.setInt(2, id)
        val updatedRows = preparedStatement.executeUpdate()
        return if (updatedRows > 0) {
            findCategoryById(id)
        } else {
            null
        }
    }

    fun deleteCategory(id: Int): Boolean {
        val sql = "DELETE FROM categories WHERE id = ?"
        val preparedStatement = connection.prepareStatement(sql)
        preparedStatement.setInt(1, id)
        val deletedRows = preparedStatement.executeUpdate()
        return deletedRows > 0
    }
}
