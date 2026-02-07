package com.ecommerce.services

import com.cloudinary.Cloudinary
import org.springframework.stereotype.Service
import org.springframework.web.multipart.MultipartFile

@Service
class CloudinaryService(private val cloudinary: Cloudinary) {

    fun uploadImage(file: MultipartFile): String {
        val uploadResult = cloudinary.uploader().upload(file.bytes, emptyMap())
        return uploadResult["url"] as String
    }
}