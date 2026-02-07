package com.ecommerce.repository

import com.ecommerce.models.Product
import com.ecommerce.models.WishlistItem
import java.sql.Connection

class WishlistRepository(private val connection: Connection) {

    fun getWishlistByUserId(userId: Int): List<WishlistItem> {
        val statement = connection.prepareStatement(
            """
            SELECT w.id, w.user_id, p.id as product_id, p.name, p.price, p.image_url
            FROM wishlists w
            JOIN products p ON w.product_id = p.id
            WHERE w.user_id = ?
            """.trimIndent()
        )
        statement.setInt(1, userId)
        val resultSet = statement.executeQuery()
        val wishlistItems = mutableListOf<WishlistItem>()

        while (resultSet.next()) {
            val product = Product(
                id = resultSet.getInt("product_id"),
                name = resultSet.getString("name"),
                price = resultSet.getBigDecimal("price"),
                imageUrl = resultSet.getString("image_url")
            )
            wishlistItems.add(
                WishlistItem(
                    id = resultSet.getInt("id"),
                    userId = resultSet.getInt("user_id"),
                    product = product
                )
            )
        }
        return wishlistItems
    }

    fun addToWishlist(userId: Int, productId: Int) {
        val statement = connection.prepareStatement("INSERT INTO wishlists (user_id, product_id) VALUES (?, ?)")
        statement.setInt(1, userId)
        statement.setInt(2, productId)
        statement.executeUpdate()
    }

    fun removeFromWishlist(userId: Int, productId: Int) {
        val statement = connection.prepareStatement("DELETE FROM wishlists WHERE user_id = ? AND product_id = ?")
        statement.setInt(1, userId)
        statement.setInt(2, productId)
        statement.executeUpdate()
    }
}