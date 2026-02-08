package com.ecommerce.features.products

import com.ecommerce.features.products.models.CreateProductRequest
import com.ecommerce.features.products.models.Product
import com.ecommerce.features.products.models.UpdateProductRequest
import java.sql.Connection
import java.sql.Statement

class ProductRepository(private val connection: Connection) {

    fun createProduct(request: CreateProductRequest): Product {
        val sql = "INSERT INTO products (title, price, description, quantity, slug, brand, category_id, discount, images) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
        val preparedStatement = connection.prepareStatement(sql, Statement.RETURN_GENERATED_KEYS)
        preparedStatement.setString(1, request.title)
        preparedStatement.setDouble(2, request.price)
        preparedStatement.setString(3, request.description)
        preparedStatement.setInt(4, request.quantity)
        preparedStatement.setString(5, request.slug)
        preparedStatement.setString(6, request.brand)
        request.categoryId?.let { preparedStatement.setInt(7, it) } ?: preparedStatement.setNull(7, java.sql.Types.INTEGER)
        request.discount?.let { preparedStatement.setDouble(8, it) } ?: preparedStatement.setNull(8, java.sql.Types.DOUBLE)
        request.images?.let { preparedStatement.setArray(9, connection.createArrayOf("text", it.toTypedArray())) } ?: preparedStatement.setNull(9, java.sql.Types.ARRAY)
        preparedStatement.executeUpdate()
        val generatedKeys = preparedStatement.generatedKeys
        generatedKeys.next()
        val id = generatedKeys.getInt(1)
        return findProductById(id)!!
    }

    fun findAllProducts(): List<Product> {
        val sql = "SELECT * FROM products"
        val statement = connection.createStatement()
        val resultSet = statement.executeQuery(sql)
        val products = mutableListOf<Product>()
        while (resultSet.next()) {
            products.add(
                Product(
                    id = resultSet.getInt("id"),
                    title = resultSet.getString("title"),
                    price = resultSet.getDouble("price"),
                    description = resultSet.getString("description"),
                    quantity = resultSet.getInt("quantity"),
                    slug = resultSet.getString("slug"),
                    brand = resultSet.getString("brand"),
                    categoryId = resultSet.getInt("category_id"),
                    sold = resultSet.getInt("sold"),
                    discount = resultSet.getDouble("discount"),
                    images = (resultSet.getArray("images")?.array as Array<String>?)?.toList(),
                    totalRatings = resultSet.getInt("total_ratings"),
                    createdAt = resultSet.getTimestamp("created_at").toLocalDateTime(),
                    updatedAt = resultSet.getTimestamp("updated_at").toLocalDateTime()
                )
            )
        }
        return products
    }

    fun findProductById(id: Int): Product? {
        val sql = "SELECT * FROM products WHERE id = ?"
        val preparedStatement = connection.prepareStatement(sql)
        preparedStatement.setInt(1, id)
        val resultSet = preparedStatement.executeQuery()
        return if (resultSet.next()) {
            Product(
                id = resultSet.getInt("id"),
                title = resultSet.getString("title"),
                price = resultSet.getDouble("price"),
                description = resultSet.getString("description"),
                quantity = resultSet.getInt("quantity"),
                slug = resultSet.getString("slug"),
                brand = resultSet.getString("brand"),
                categoryId = resultSet.getInt("category_id"),
                sold = resultSet.getInt("sold"),
                discount = resultSet.getDouble("discount"),
                images = (resultSet.getArray("images")?.array as Array<String>?)?.toList(),
                totalRatings = resultSet.getInt("total_ratings"),
                createdAt = resultSet.getTimestamp("created_at").toLocalDateTime(),
                updatedAt = resultSet.getTimestamp("updated_at").toLocalDateTime()
            )
        } else {
            null
        }
    }

    fun updateProduct(id: Int, request: UpdateProductRequest): Product? {
        val sql = "UPDATE products SET title = ?, price = ?, description = ?, quantity = ?, slug = ?, brand = ?, category_id = ?, discount = ?, images = ? WHERE id = ?"
        val preparedStatement = connection.prepareStatement(sql)
        preparedStatement.setString(1, request.title)
        preparedStatement.setDouble(2, request.price)
        preparedStatement.setString(3, request.description)
        preparedStatement.setInt(4, request.quantity)
        preparedStatement.setString(5, request.slug)
        preparedStatement.setString(6, request.brand)
        request.categoryId?.let { preparedStatement.setInt(7, it) } ?: preparedStatement.setNull(7, java.sql.Types.INTEGER)
        request.discount?.let { preparedStatement.setDouble(8, it) } ?: preparedStatement.setNull(8, java.sql.Types.DOUBLE)
        request.images?.let { preparedStatement.setArray(9, connection.createArrayOf("text", it.toTypedArray())) } ?: preparedStatement.setNull(9, java.sql.Types.ARRAY)
        preparedStatement.setInt(10, id)
        val updatedRows = preparedStatement.executeUpdate()
        return if (updatedRows > 0) {
            findProductById(id)
        } else {
            null
        }
    }

    fun deleteProduct(id: Int): Boolean {
        val sql = "DELETE FROM products WHERE id = ?"
        val preparedStatement = connection.prepareStatement(sql)
        preparedStatement.setInt(1, id)
        val deletedRows = preparedStatement.executeUpdate()
        return deletedRows > 0
    }
}
