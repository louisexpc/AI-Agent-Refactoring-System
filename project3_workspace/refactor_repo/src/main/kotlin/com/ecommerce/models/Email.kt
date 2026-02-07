package com.ecommerce.models

data class Email(
    val to: String,
    val subject: String,
    val text: String
)