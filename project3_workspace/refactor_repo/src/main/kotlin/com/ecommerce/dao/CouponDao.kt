package com.ecommerce.dao

import com.ecommerce.models.Coupon
import java.time.LocalDateTime

interface CouponDao {
    suspend fun createCoupon(code: String, discountPercentage: Double, expiryDate: LocalDateTime): Coupon?
    suspend fun getCoupon(id: Int): Coupon?
    suspend fun updateCoupon(id: Int, code: String?, discountPercentage: Double?, expiryDate: LocalDateTime?): Boolean
    suspend fun deleteCoupon(id: Int): Boolean
}
