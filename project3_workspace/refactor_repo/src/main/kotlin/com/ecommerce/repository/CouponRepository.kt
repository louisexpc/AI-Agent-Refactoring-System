package com.ecommerce.repository

import com.ecommerce.models.Coupon
import java.sql.Connection

class CouponRepository(private val connection: Connection) {

    fun createCoupon(coupon: Coupon): Coupon {
        val statement = connection.prepareStatement("INSERT INTO coupons (name, expiry, discount) VALUES (?, ?, ?)", java.sql.Statement.RETURN_GENERATED_KEYS)
        statement.setString(1, coupon.name)
        statement.setTimestamp(2, java.sql.Timestamp(coupon.expiry.time))
        statement.setBigDecimal(3, coupon.discount)
        statement.executeUpdate()
        val generatedKeys = statement.generatedKeys
        if (generatedKeys.next()) {
            coupon.id = generatedKeys.getInt(1)
        }
        return coupon
    }

    fun getAllCoupons(): List<Coupon> {
        val statement = connection.prepareStatement("SELECT * FROM coupons")
        val resultSet = statement.executeQuery()
        val coupons = mutableListOf<Coupon>()
        while (resultSet.next()) {
            coupons.add(
                Coupon(
                    id = resultSet.getInt("id"),
                    name = resultSet.getString("name"),
                    expiry = resultSet.getTimestamp("expiry"),
                    discount = resultSet.getBigDecimal("discount")
                )
            )
        }
        return coupons
    }

    fun updateCoupon(id: Int, coupon: Coupon): Coupon? {
        val statement = connection.prepareStatement("UPDATE coupons SET name = ?, expiry = ?, discount = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?")
        statement.setString(1, coupon.name)
        statement.setTimestamp(2, java.sql.Timestamp(coupon.expiry.time))
        statement.setBigDecimal(3, coupon.discount)
        statement.setInt(4, id)
        val updatedRows = statement.executeUpdate()
        return if (updatedRows > 0) getCouponById(id) else null
    }

    fun deleteCoupon(id: Int): Boolean {
        val statement = connection.prepareStatement("DELETE FROM coupons WHERE id = ?")
        statement.setInt(1, id)
        return statement.executeUpdate() > 0
    }

    fun getCouponById(id: Int): Coupon? {
        val statement = connection.prepareStatement("SELECT * FROM coupons WHERE id = ?")
        statement.setInt(1, id)
        val resultSet = statement.executeQuery()
        return if (resultSet.next()) {
            Coupon(
                id = resultSet.getInt("id"),
                name = resultSet.getString("name"),
                expiry = resultSet.getTimestamp("expiry"),
                discount = resultSet.getBigDecimal("discount")
            )
        } else {
            null
        }
    }
}
