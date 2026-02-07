package com.ecommerce.routes

import com.ecommerce.models.Coupon
import com.ecommerce.repository.CouponRepository
import io.ktor.server.application.*
import io.ktor.server.request.*
import io.ktor.server.response.*
import io.ktor.server.routing.*

fun Route.couponRoutes(couponRepository: CouponRepository) {
    route("/api/coupon") {
        post {
            val coupon = call.receive<Coupon>()
            val createdCoupon = couponRepository.createCoupon(coupon)
            call.respond(createdCoupon)
        }

        get {
            val coupons = couponRepository.getAllCoupons()
            call.respond(coupons)
        }

        get("/{id}") {
            val id = call.parameters["id"]?.toIntOrNull()
            if (id != null) {
                val coupon = couponRepository.getCouponById(id)
                if (coupon != null) {
                    call.respond(coupon)
                } else {
                    call.respondText("Coupon not found", status = io.ktor.http.HttpStatusCode.NotFound)
                }
            } else {
                call.respondText("Invalid ID", status = io.ktor.http.HttpStatusCode.BadRequest)
            }
        }

        put("/{id}") {
            val id = call.parameters["id"]?.toIntOrNull()
            val coupon = call.receive<Coupon>()
            if (id != null) {
                val updatedCoupon = couponRepository.updateCoupon(id, coupon)
                if (updatedCoupon != null) {
                    call.respond(updatedCoupon)
                } else {
                    call.respondText("Coupon not found", status = io.ktor.http.HttpStatusCode.NotFound)
                }
            } else {
                call.respondText("Invalid ID", status = io.ktor.http.HttpStatusCode.BadRequest)
            }
        }

        delete("/{id}") {
            val id = call.parameters["id"]?.toIntOrNull()
            if (id != null) {
                if (couponRepository.deleteCoupon(id)) {
                    call.respondText("Coupon deleted successfully")
                } else {
                    call.respondText("Coupon not found", status = io.ktor.http.HttpStatusCode.NotFound)
                }
            } else {
                call.respondText("Invalid ID", status = io.ktor.http.HttpStatusCode.BadRequest)
            }
        }
    }
}
