package com.ecommerce.controllers

import com.ecommerce.dao.CouponDao
import io.ktor.http.* 
import io.ktor.server.application.* 
import io.ktor.server.request.* 
import io.ktor.server.response.* 
import java.time.LocalDateTime
import java.time.format.DateTimeFormatter

class CouponController(private val couponDao: CouponDao) {

    private val formatter = DateTimeFormatter.ofPattern("dd-MM-yyyy HH")

    suspend fun createCoupon(call: ApplicationCall) {
        val parameters = call.receive<Parameters>()
        val code = parameters["code"] ?: return call.respond(HttpStatusCode.BadRequest, "Missing code")
        val discountPercentage = parameters["discountPercentage"]?.toDoubleOrNull() ?: return call.respond(HttpStatusCode.BadRequest, "Invalid discount percentage")
        val expiryDateStr = parameters["expiryDate"] ?: return call.respond(HttpStatusCode.BadRequest, "Missing expiry date")

        val expiryDate = try {
            LocalDateTime.parse(expiryDateStr, formatter)
        } catch (e: Exception) {
            return call.respond(HttpStatusCode.BadRequest, "Invalid date format. Use 'dd-MM-yyyy HH'")
        }

        if (expiryDate.isBefore(LocalDateTime.now())) {
            return call.respond(HttpStatusCode.BadRequest, "Expiry date must be in the future")
        }

        val coupon = couponDao.createCoupon(code.uppercase(), discountPercentage, expiryDate)
        if (coupon != null) {
            call.respond(HttpStatusCode.Created, coupon)
        } else {
            call.respond(HttpStatusCode.InternalServerError, "Failed to create coupon")
        }
    }

    suspend fun updateCoupon(call: ApplicationCall) {
        val id = call.parameters["id"]?.toIntOrNull() ?: return call.respond(HttpStatusCode.BadRequest, "Invalid coupon ID")
        val parameters = call.receive<Parameters>()
        val code = parameters["code"]
        val discountPercentage = parameters["discountPercentage"]?.toDoubleOrNull()
        val expiryDateStr = parameters["expiryDate"]

        val expiryDate = expiryDateStr?.let {
            try {
                LocalDateTime.parse(it, formatter)
            } catch (e: Exception) {
                return@updateCoupon call.respond(HttpStatusCode.BadRequest, "Invalid date format. Use 'dd-MM-yyyy HH'")
            }
        }

        if (expiryDate != null && expiryDate.isBefore(LocalDateTime.now())) {
            return call.respond(HttpStatusCode.BadRequest, "Expiry date must be in the future")
        }

        val success = couponDao.updateCoupon(id, code?.uppercase(), discountPercentage, expiryDate)
        if (success) {
            call.respond(HttpStatusCode.OK, "Coupon updated successfully")
        } else {
            call.respond(HttpStatusCode.InternalServerError, "Failed to update coupon")
        }
    }

    suspend fun deleteCoupon(call: ApplicationCall) {
        val id = call.parameters["id"]?.toIntOrNull() ?: return call.respond(HttpStatusCode.BadRequest, "Invalid coupon ID")
        val success = couponDao.deleteCoupon(id)
        if (success) {
            call.respond(HttpStatusCode.OK, "Coupon deleted successfully")
        } else {
            call.respond(HttpStatusCode.NotFound, "Coupon not found")
        }
    }
}
