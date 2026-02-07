package com.example.ecommerce.controller

import com.example.ecommerce.model.Coupon
import org.springframework.web.bind.annotation.*

@RestController
@RequestMapping("/coupons")
class CouponController {

    // Dummy data
    private val coupons = mutableListOf(
        Coupon(1, "SUMMER10", 10.0),
        Coupon(2, "WINTER20", 20.0)
    )

    @GetMapping
    fun getAllCoupons(): List<Coupon> {
        return coupons
    }

    @GetMapping("/{code}")
    fun getCouponByCode(@PathVariable code: String): Coupon? {
        return coupons.find { it.code == code }
    }

    @PostMapping
    fun createCoupon(@RequestBody coupon: Coupon): Coupon {
        coupons.add(coupon)
        return coupon
    }
}

data class Coupon(val id: Long, val code: String, val discount: Double)