package com.example.ecommerce.repository

import com.example.ecommerce.model.Product

class ProductRepository {

    fun save(product: Product): Product {
        //language=SQL
        val sql = """
            INSERT INTO products (title, slug, description, price, category, brand, quantity, sold, images, color, total_rating)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
        // Execute SQL
        return product
    }

    fun findById(id: Long): Product? {
        //language=SQL
        val sql = "SELECT * FROM products WHERE id = ?"
        // Execute SQL
        return null
    }

    fun findAll(): List<Product> {
        //language=SQL
        val sql = "SELECT * FROM products"
        // Execute SQL
        return emptyList()
    }

    fun update(product: Product): Product {
        //language=SQL
        val sql = """
            UPDATE products
            SET title = ?, slug = ?, description = ?, price = ?, category = ?, brand = ?, quantity = ?, sold = ?, images = ?, color = ?, total_rating = ?
            WHERE id = ?
            """
        // Execute SQL
        return product
    }

    fun deleteById(id: Long) {
        //language=SQL
        val sql = "DELETE FROM products WHERE id = ?"
        // Execute SQL
    }
}
