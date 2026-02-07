package com.ecommerce.repository

import com.ecommerce.models.Cart
import com.ecommerce.models.CartItem
import com.ecommerce.models.Product
import java.sql.Connection

class CartRepository(private val connection: Connection) {

    fun getCartByUserId(userId: Int): Cart? {
        val statement = connection.prepareStatement("SELECT id, user_id, created_at, updated_at FROM carts WHERE user_id = ?")
        statement.setInt(1, userId)
        val resultSet = statement.executeQuery()

        return if (resultSet.next()) {
            val cart = Cart(
                id = resultSet.getInt("id"),
                userId = resultSet.getInt("user_id"),
                createdAt = resultSet.getTimestamp("created_at"),
                updatedAt = resultSet.getTimestamp("updated_at")
            )
            cart.items.addAll(getCartItems(cart.id))
            cart
        } else {
            null
        }
    }

    fun createCart(userId: Int): Cart {
        val statement = connection.prepareStatement("INSERT INTO carts (user_id) VALUES (?)", java.sql.Statement.RETURN_GENERATED_KEYS)
        statement.setInt(1, userId)
        statement.executeUpdate()
        val generatedKeys = statement.generatedKeys
        if (generatedKeys.next()) {
            return getCartByUserId(userId)!!
        } else {
            throw Exception("Failed to create cart")
        }
    }

    fun getCartItems(cartId: Int): List<CartItem> {
        val statement = connection.prepareStatement(
            """
            SELECT ci.id, ci.cart_id, ci.quantity, p.id as product_id, p.name, p.price, p.image_url
            FROM cart_items ci
            JOIN products p ON ci.product_id = p.id
            WHERE ci.cart_id = ?
            """.trimIndent()
        )
        statement.setInt(1, cartId)
        val resultSet = statement.executeQuery()
        val cartItems = mutableListOf<CartItem>()

        while (resultSet.next()) {
            val product = Product(
                id = resultSet.getInt("product_id"),
                name = resultSet.getString("name"),
                price = resultSet.getBigDecimal("price"),
                imageUrl = resultSet.getString("image_url")
            )
            cartItems.add(
                CartItem(
                    id = resultSet.getInt("id"),
                    cartId = resultSet.getInt("cart_id"),
                    product = product,
                    quantity = resultSet.getInt("quantity")
                )
            )
        }
        return cartItems
    }

    fun addOrUpdateItem(cartId: Int, productId: Int, quantity: Int) {
        val statement = connection.prepareStatement(
            """
            INSERT INTO cart_items (cart_id, product_id, quantity)
            VALUES (?, ?, ?)
            ON CONFLICT (cart_id, product_id)
            DO UPDATE SET quantity = cart_items.quantity + ?;
            """.trimIndent()
        )
        statement.setInt(1, cartId)
        statement.setInt(2, productId)
        statement.setInt(3, quantity)
        statement.setInt(4, quantity)
        statement.executeUpdate()
    }

    fun removeItem(cartId: Int, productId: Int) {
        val statement = connection.prepareStatement("DELETE FROM cart_items WHERE cart_id = ? AND product_id = ?")
        statement.setInt(1, cartId)
        statement.setInt(2, productId)
        statement.executeUpdate()
    }

    fun clearCart(cartId: Int) {
        val statement = connection.prepareStatement("DELETE FROM cart_items WHERE cart_id = ?")
        statement.setInt(1, cartId)
        statement.executeUpdate()
    }
}