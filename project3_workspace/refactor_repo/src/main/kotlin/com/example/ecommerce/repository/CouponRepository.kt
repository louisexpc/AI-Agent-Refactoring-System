package com.example.ecommerce.repository

import com.example.ecommerce.model.Coupon

class CouponRepository {

    fun save(coupon: Coupon): Coupon {
        //language=SQL
        val sql = "INSERT INTO coupons (name, expiry, discount) VALUES (?, ?, ?)"
        // Execute SQL
        return coupon
    }

    fun findById(id: Long): Coupon? {
        //language=SQL
        val sql = "SELECT * FROM coupons WHERE id = ?"
        // Execute SQL
        return null
    }

    fun findByName(name: String): Coupon? {
        //language=SQL
        val sql = "SELECT * FROM coupons WHERE name = ?"
        // Execute SQL
        return null
    }

    fun findAll(): List<Coupon> {
        //language=SQL
        val sql = "SELECT * FROM coupons"
        // Execute SQL
        return emptyList()
    }

    fun update(coupon: Coupon): Coupon {
        //language=SQL
        val sql = "UPDATE coupons SET name = ?, expiry = ?, discount = ? WHERE id = ?"
        // Execute SQL
        return coupon
    }

    fun deleteById(id: Long) {
        //language=SQL
        val sql = "DELETE FROM coupons WHERE id = ?"
        // Execute SQL
    }
}
