package com.example.ecommerce.repository

import com.example.ecommerce.model.User

class UserRepository {

    fun save(user: User): User {
        //language=SQL
        val sql = """
            INSERT INTO users (firstname, lastname, email, mobile, password_hash, role, is_blocked, address, refresh_token, password_changed_at, password_reset_token, password_reset_expires)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
        // Execute SQL
        return user
    }

    fun findById(id: Long): User? {
        //language=SQL
        val sql = "SELECT * FROM users WHERE id = ?"
        // Execute SQL
        return null
    }

    fun findByEmail(email: String): User? {
        //language=SQL
        val sql = "SELECT * FROM users WHERE email = ?"
        // Execute SQL
        return null
    }

    fun update(user: User): User {
        //language=SQL
        val sql = """
            UPDATE users
            SET firstname = ?, lastname = ?, email = ?, mobile = ?, password_hash = ?, role = ?, is_blocked = ?, address = ?, refresh_token = ?, password_changed_at = ?, password_reset_token = ?, password_reset_expires = ?
            WHERE id = ?
            """
        // Execute SQL
        return user
    }

    fun deleteById(id: Long) {
        //language=SQL
        val sql = "DELETE FROM users WHERE id = ?"
        // Execute SQL
    }
}
