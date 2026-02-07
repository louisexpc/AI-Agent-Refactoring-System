package com.ecommerce.features.cart

import com.ecommerce.features.cart.models.Cart
import com.ecommerce.features.cart.models.CartItem
import com.ecommerce.shared.database.Database
import java.sql.Statement

class CartRepository(private val database: Database) {

    fun getCartByUserId(userId: Int): Cart? {
        val sql = "SELECT * FROM carts WHERE user_id = ?"
        return database.connection().use { conn ->
            conn.prepareStatement(sql).use { stmt ->
                stmt.setInt(1, userId)
                stmt.executeQuery().use { rs ->
                    if (rs.next()) {
                        Cart(
                            id = rs.getInt("id"),
                            userId = rs.getInt("user_id"),
                        )
                    } else {
                        null
                    }
                }
            }
        }
    }

    fun createCart(userId: Int): Cart {
        val sql = "INSERT INTO carts (user_id) VALUES (?)"
        return database.connection().use { conn ->
            conn.prepareStatement(sql, Statement.RETURN_GENERATED_KEYS).use { stmt ->
                stmt.setInt(1, userId)
                stmt.executeUpdate()
                stmt.generatedKeys.use { rs ->
                    rs.next()
                    val id = rs.getInt(1)
                    Cart(id, userId)
                }
            }
        }
    }

    fun getCartItems(cartId: Int): List<CartItem> {
        val sql = "SELECT * FROM cart_items WHERE cart_id = ?"
        return database.connection().use { conn ->
            conn.prepareStatement(sql).use { stmt ->
                stmt.setInt(1, cartId)
                stmt.executeQuery().use { rs ->
                    val items = mutableListOf<CartItem>()
                    while (rs.next()) {
                        items.add(
                            CartItem(
                                id = rs.getInt("id"),
                                cartId = rs.getInt("cart_id"),
                                productId = rs.getInt("product_id"),
                                quantity = rs.getInt("quantity"),
                            )
                        )
                    }
                    items
                }
            }
        }
    }

    fun getCartItem(cartId: Int, productId: Int): CartItem? {
        val sql = "SELECT * FROM cart_items WHERE cart_id = ? AND product_id = ?"
        return database.connection().use { conn ->
            conn.prepareStatement(sql).use { stmt ->
                stmt.setInt(1, cartId)
                stmt.setInt(2, productId)
                stmt.executeQuery().use { rs ->
                    if (rs.next()) {
                        CartItem(
                            id = rs.getInt("id"),
                            cartId = rs.getInt("cart_id"),
                            productId = rs.getInt("product_id"),
                            quantity = rs.getInt("quantity"),
                        )
                    } else {
                        null
                    }
                }
            }
        }
    }

    fun addCartItem(cartId: Int, productId: Int, quantity: Int): CartItem {
        val sql = "INSERT INTO cart_items (cart_id, product_id, quantity) VALUES (?, ?, ?)"
        return database.connection().use { conn ->
            conn.prepareStatement(sql, Statement.RETURN_GENERATED_KEYS).use { stmt ->
                stmt.setInt(1, cartId)
                stmt.setInt(2, productId)
                stmt.setInt(3, quantity)
                stmt.executeUpdate()
                stmt.generatedKeys.use { rs ->
                    rs.next()
                    val id = rs.getInt(1)
                    CartItem(id, cartId, productId, quantity)
                }
            }
        }
    }

    fun updateCartItem(cartId: Int, productId: Int, quantity: Int) {
        val sql = "UPDATE cart_items SET quantity = ? WHERE cart_id = ? AND product_id = ?"
        database.connection().use { conn ->
            conn.prepareStatement(sql).use { stmt ->
                stmt.setInt(1, quantity)
                stmt.setInt(2, cartId)
                stmt.setInt(3, productId)
                stmt.executeUpdate()
            }
        }
    }

    fun removeCartItem(cartId: Int, productId: Int) {
        val sql = "DELETE FROM cart_items WHERE cart_id = ? AND product_id = ?"
        database.connection().use { conn ->
            conn.prepareStatement(sql).use { stmt ->
                stmt.setInt(1, cartId)
                stmt.setInt(2, productId)
                stmt.executeUpdate()
            }
        }
    }

    fun clearCart(cartId: Int) {
        val sql = "DELETE FROM cart_items WHERE cart_id = ?"
        database.connection().use { conn ->
            conn.prepareStatement(sql).use { stmt ->
                stmt.setInt(1, cartId)
                stmt.executeUpdate()
            }
        }
    }
}
