package com.ecommerce.models

import java.math.BigDecimal

data class OrderItem(
    var id: Int = 0,
    var orderId: Int = 0,
    val productId: Int,
    val quantity: Int,
    val price: BigDecimal
)
