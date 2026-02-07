package com.ecommerce.repository

import java.sql.Connection
import java.sql.Statement

data class Product(
    var id: Int? = null,
    val name: String,
    val description: String,
    val price: Double,
    val stock: Int,
    val categoryId: Int
)

data class ProductImage(
    var id: Int? = null,
    val productId: Int,
    val imageUrl: String
)

class ProductRepository(private val connection: Connection) {

    fun createProduct(product: Product): Product {
        val sql = "INSERT INTO products (name, description, price, stock, category_id) VALUES (?, ?, ?, ?, ?)"
        val statement = connection.prepareStatement(sql, Statement.RETURN_GENERATED_KEYS)
        statement.setString(1, product.name)
        statement.setString(2, product.description)
        statement.setDouble(3, product.price)
        statement.setInt(4, product.stock)
        statement.setInt(5, product.categoryId)
        statement.executeUpdate()

        val generatedKeys = statement.generatedKeys
        if (generatedKeys.next()) {
            product.id = generatedKeys.getInt(1)
        }
        return product
    }

    fun getAllProducts(): List<Product> {
        val products = mutableListOf<Product>()
        val sql = "SELECT * FROM products"
        val statement = connection.prepareStatement(sql)
        val resultSet = statement.executeQuery()

        while (resultSet.next()) {
            products.add(
                Product(
                    id = resultSet.getInt("id"),
                    name = resultSet.getString("name"),
                    description = resultSet.getString("description"),
                    price = resultSet.getDouble("price"),
                    stock = resultSet.getInt("stock"),
                    categoryId = resultSet.getInt("category_id")
                )
            )
        }
        return products
    }

    fun getProductById(id: Int): Product? {
        val sql = "SELECT * FROM products WHERE id = ?"
        val statement = connection.prepareStatement(sql)
        statement.setInt(1, id)
        val resultSet = statement.executeQuery()

        return if (resultSet.next()) {
            Product(
                id = resultSet.getInt("id"),
                name = resultSet.getString("name"),
                description = resultSet.getString("description"),
                price = resultSet.getDouble("price"),
                stock = resultSet.getInt("stock"),
                categoryId = resultSet.getInt("category_id")
            )
        } else {
            null
        }
    }

    fun updateProduct(id: Int, product: Product): Boolean {
        val sql = "UPDATE products SET name = ?, description = ?, price = ?, stock = ?, category_id = ? WHERE id = ?"
        val statement = connection.prepareStatement(sql)
        statement.setString(1, product.name)
        statement.setString(2, product.description)
        statement.setDouble(3, product.price)
        statement.setInt(4, product.stock)
        statement.setInt(5, product.categoryId)
        statement.setInt(6, id)
        return statement.executeUpdate() > 0
    }

    fun deleteProduct(id: Int): Boolean {
        val sql = "DELETE FROM products WHERE id = ?"
        val statement = connection.prepareStatement(sql)
        statement.setInt(1, id)
        return statement.executeUpdate() > 0
    }

    fun addImageToProduct(productId: Int, imageUrl: String): ProductImage {
        val sql = "INSERT INTO product_images (product_id, image_url) VALUES (?, ?)"
        val statement = connection.prepareStatement(sql, Statement.RETURN_GENERATED_KEYS)
        statement.setInt(1, productId)
        statement.setString(2, imageUrl)
        statement.executeUpdate()

        val generatedKeys = statement.generatedKeys
        val productImage = ProductImage(productId = productId, imageUrl = imageUrl)
        if (generatedKeys.next()) {
            productImage.id = generatedKeys.getInt(1)
        }
        return productImage
    }
}
