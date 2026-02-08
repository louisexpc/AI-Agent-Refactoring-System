package com.ecommerce.services

import com.ecommerce.models.Email
import org.springframework.mail.SimpleMailMessage
import org.springframework.mail.javamail.JavaMailSender
import org.springframework.stereotype.Service

@Service
class EmailService(private val mailSender: JavaMailSender) {

    fun sendEmail(email: Email) {
        val message = SimpleMailMessage()
        message.setTo(email.to)
        message.setSubject(email.subject)
        message.setText(email.text)
        mailSender.send(message)
    }
}