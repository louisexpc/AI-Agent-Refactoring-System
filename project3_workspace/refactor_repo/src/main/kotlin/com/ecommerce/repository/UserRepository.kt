
package com.ecommerce.repository

import com.ecommerce.models.User
import com.ecommerce.models.UserRole
import java.sql.Connection
import java.sql.Statement

class UserRepository(private val connection: Connection) {

    fun createUser(user: User): User {
        val statement = connection.prepareStatement("INSERT INTO users (first_name, last_name, email, mobile, password, role) VALUES (?, ?, ?, ?, ?, ?)", Statement.RETURN_GENERATED_KEYS)
        statement.setString(1, user.firstName)
        statement.setString(2, user.lastName)
        statement.setString(3, user.email)
        statement.setString(4, user.mobile)
        statement.setString(5, user.password)
        statement.setString(6, user.role.name)
        statement.executeUpdate()

        val generatedKeys = statement.generatedKeys
        if (generatedKeys.next()) {
            return user.copy(id = generatedKeys.getInt(1))
        } else {
            throw Exception("Failed to create user, no ID obtained.")
        }
    }

    fun findByEmail(email: String): User? {
        val statement = connection.prepareStatement("SELECT * FROM users WHERE email = ?")
        statement.setString(1, email)
        val resultSet = statement.executeQuery()

        return if (resultSet.next()) {
            User(
                id = resultSet.getInt("id"),
                firstName = resultSet.getString("first_name"),
                lastName = resultSet.getString("last_name"),
                email = resultSet.getString("email"),
                mobile = resultSet.getString("mobile"),
                password = resultSet.getString("password"),
                role = UserRole.valueOf(resultSet.getString("role"))
            )
        } else {
            null
        }
    }

    fun findById(id: Int): User? {
        val statement = connection.prepareStatement("SELECT * FROM users WHERE id = ?")
        statement.setInt(1, id)
        val resultSet = statement.executeQuery()

        return if (resultSet.next()) {
            User(
                id = resultSet.getInt("id"),
                firstName = resultSet.getString("first_name"),
                lastName = resultSet.getString("last_name"),
                email = resultSet.getString("email"),
                mobile = resultSet.getString("mobile"),
                password = resultSet.getString("password"),
                role = UserRole.valueOf(resultSet.getString("role"))
            )
        } else {
            null
        }
    }

    fun updateUser(id: Int, user: User) {
        val statement = connection.prepareStatement("UPDATE users SET first_name = ?, last_name = ?, email = ?, mobile = ? WHERE id = ?")
        statement.setString(1, user.firstName)
        statement.setString(2, user.lastName)
        statement.setString(3, user.email)
        statement.setString(4, user.mobile)
        statement.setInt(5, id)
        statement.executeUpdate()
    }

    fun deleteUser(id: Int) {
        val statement = connection.prepareStatement("DELETE FROM users WHERE id = ?")
        statement.setInt(1, id)
        statement.executeUpdate()
    }
}
