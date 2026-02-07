package com.ecommerce.dao

import com.ecommerce.models.Product
import java.sql.Connection
import java.sql.Statement

class ProductDao(private val connection: Connection) {

    fun createTable() {
        val query = """
            CREATE TABLE IF NOT EXISTS products (
                id SERIAL PRIMARY KEY,
                title VARCHAR(255) NOT NULL,
                price NUMERIC(10, 2) NOT NULL,
                description TEXT NOT NULL,
                quantity INT NOT NULL,
                slug VARCHAR(255) NOT NULL,
                brand VARCHAR(255),
                categoryId INT REFERENCES categories(id),
                sold INT DEFAULT 0,
                discount NUMERIC(10, 2),
                createdAt TIMESTAMP NOT NULL,
                updatedAt TIMESTAMP NOT NULL
            )
            """
        connection.createStatement().use { it.execute(query) }
    }

    fun create(product: Product): Product {
        val query = "INSERT INTO products (title, price, description, quantity, slug, brand, categoryId, sold, discount, createdAt, updatedAt) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
        val preparedStatement = connection.prepareStatement(query, Statement.RETURN_GENERATED_KEYS)
        preparedStatement.setString(1, product.title)
        preparedStatement.setDouble(2, product.price)
        preparedStatement.setString(3, product.description)
        preparedStatement.setInt(4, product.quantity)
        preparedStatement.setString(5, product.slug)
        preparedStatement.setString(6, product.brand)
        product.categoryId?.let { preparedStatement.setInt(7, it) } ?: preparedStatement.setNull(7, java.sql.Types.INTEGER)
        preparedStatement.setInt(8, product.sold)
        product.discount?.let { preparedStatement.setDouble(9, it) } ?: preparedStatement.setNull(9, java.sql.Types.NUMERIC)
        preparedStatement.setTimestamp(10, java.sql.Timestamp.valueOf(product.createdAt))
        preparedStatement.setTimestamp(11, java.sql.Timestamp.valueOf(product.updatedAt))
        preparedStatement.executeUpdate()
        val generatedKeys = preparedStatement.resultSet
        if (generatedKeys.next()) {
            return product.copy(id = generatedKeys.getInt(1))
        }
        throw Exception("Failed to create product")
    }

    fun findById(id: Int): Product? {
        val query = "SELECT * FROM products WHERE id = ?"
        val preparedStatement = connection.prepareStatement(query)
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
                categoryId = resultSet.getInt("categoryId"),
                sold = resultSet.getInt("sold"),
                discount = resultSet.getDouble("discount"),
                createdAt = resultSet.getTimestamp("createdAt").toLocalDateTime(),
                updatedAt = resultSet.getTimestamp("updatedAt").toLocalDateTime()
            )
        } else {
            null
        }
    }

    fun findAll(): List<Product> {
        val query = "SELECT * FROM products"
        val statement = connection.createStatement()
        val resultSet = statement.executeQuery(query)
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
                    categoryId = resultSet.getInt("categoryId"),
                    sold = resultSet.getInt("sold"),
                    discount = resultSet.getDouble("discount"),
                    createdAt = resultSet.getTimestamp("createdAt").toLocalDateTime(),
                    updatedAt = resultSet.getTimestamp("updatedAt").toLocalDateTime()
                )
            )
        }
        return products
    }

    fun update(product: Product) {
        val query = "UPDATE products SET title = ?, price = ?, description = ?, quantity = ?, slug = ?, brand = ?, categoryId = ?, sold = ?, discount = ?, updatedAt = ? WHERE id = ?"
        val preparedStatement = connection.prepareStatement(query)
        preparedStatement.setString(1, product.title)
        preparedStatement.setDouble(2, product.price)
        preparedStatement.setString(3, product.description)
        preparedStatement.setInt(4, product.quantity)
        preparedStatement.setString(5, product.slug)
        preparedStatement.setString(6, product.brand)
        product.categoryId?.let { preparedStatement.setInt(7, it) } ?: preparedStatement.setNull(7, java.sql.Types.INTEGER)
        preparedStatement.setInt(8, product.sold)
        product.discount?.let { preparedStatement.setDouble(9, it) } ?: preparedStatement.setNull(9, java.sql.Types.NUMERIC)
        preparedStatement.setTimestamp(10, java.sql.Timestamp.valueOf(product.updatedAt))
        preparedStatement.setInt(11, product.id)
        preparedStatement.executeUpdate()
    }

    fun delete(id: Int) {
        val query = "DELETE FROM products WHERE id = ?"
        val preparedStatement = connection.prepareStatement(query)
        preparedStatement.setInt(1, id)
        preparedStatement.executeUpdate()
    }
}
