package com.ecommerce.features.cart

import com.ecommerce.features.cart.models.CartItemResponse
import com.ecommerce.features.cart.models.CartResponse
import com.ecommerce.features.product.ProductRepository

class CartService(
    private val cartRepository: CartRepository,
    private val productRepository: ProductRepository,
) {

    suspend fun getCart(userId: Int): CartResponse? {
        val cart = cartRepository.getCartByUserId(userId) ?: return null
        val cartItems = cartRepository.getCartItems(cart.id)
        val productIds = cartItems.map { it.productId }
        val products = productRepository.getProductsByIds(productIds)

        val cartItemResponses = cartItems.map { cartItem ->
            val product = products.find { it.id == cartItem.productId }!!
            CartItemResponse(product, cartItem.quantity)
        }

        return CartResponse(cart.id, cart.userId, cartItemResponses)
    }

    fun addItemToCart(userId: Int, productId: Int, quantity: Int) {
        var cart = cartRepository.getCartByUserId(userId)
        if (cart == null) {
            cart = cartRepository.createCart(userId)
        }

        val cartItem = cartRepository.getCartItem(cart.id, productId)
        if (cartItem != null) {
            val newQuantity = cartItem.quantity + quantity
            cartRepository.updateCartItem(cart.id, productId, newQuantity)
        } else {
            cartRepository.addCartItem(cart.id, productId, quantity)
        }
    }

    fun updateCartItem(userId: Int, productId: Int, quantity: Int) {
        val cart = cartRepository.getCartByUserId(userId) ?: return
        cartRepository.updateCartItem(cart.id, productId, quantity)
    }

    fun removeItemFromCart(userId: Int, productId: Int) {
        val cart = cartRepository.getCartByUserId(userId) ?: return
        cartRepository.removeCartItem(cart.id, productId)
    }

    fun clearCart(userId: Int) {
        val cart = cartRepository.getCartByUserId(userId) ?: return
        cartRepository.clearCart(cart.id)
    }
}
