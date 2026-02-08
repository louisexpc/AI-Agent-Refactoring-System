package com.ecommerce.dao

import com.ecommerce.models.Cart
import com.ecommerce.models.CartItem

interface CartDao {
    suspend fun create(userId: Int): Cart
    suspend fun getByUserId(userId: Int): Cart?
    suspend fun addItem(cartId: Int, productId: Int, quantity: Int): CartItem
    suspend fun updateItem(cartId: Int, productId: Int, quantity: Int)
    suspend fun clear(cartId: Int)
    suspend fun getCart(userId: Int): Cart?
}
