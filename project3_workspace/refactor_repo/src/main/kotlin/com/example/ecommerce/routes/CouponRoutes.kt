package com.example.ecommerce.routes

import com.example.ecommerce.controller.CouponController
import io.ktor.server.application.*
import io.ktor.server.request.*
import io.ktor.server.response.*
import io.ktor.server.routing.*

fun Route.couponRouting() {
    val couponController = CouponController()

    route("/coupons") {
        get {
            call.respond(couponController.getAllCoupons())
        }
        get("{code}") {
            val code = call.parameters["code"] ?: return@get call.respondText("Missing code")
            val coupon = couponController.getCouponByCode(code)
            if (coupon != null) {
                call.respond(coupon)
            } else {
                call.respondText("Coupon not found")
            }
        }
        post {
            val coupon = call.receive<com.example.ecommerce.controller.Coupon>()
            call.respond(couponController.createCoupon(coupon))
        }
    }
}
