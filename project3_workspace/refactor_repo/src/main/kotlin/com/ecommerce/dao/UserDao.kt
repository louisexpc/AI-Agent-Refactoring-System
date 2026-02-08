package com.ecommerce.dao

import com.ecommerce.models.User
import java.sql.Connection
import java.sql.Statement

class UserDao(private val connection: Connection) {

    fun createTable() {
        val query = """
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                firstName VARCHAR(255) NOT NULL,
                lastName VARCHAR(255) NOT NULL,
                email VARCHAR(255) UNIQUE NOT NULL,
                mobile VARCHAR(255) UNIQUE NOT NULL,
                passwordHash VARCHAR(255) NOT NULL,
                passwordChangedAt TIMESTAMP,
                passwordResetToken VARCHAR(255),
                passwordResetExpires TIMESTAMP,
                role VARCHAR(50) DEFAULT 'user',
                isBlocked BOOLEAN DEFAULT false
            )
            """
        connection.createStatement().use { it.execute(query) }
    }

    fun create(user: User): User {
        val query = "INSERT INTO users (firstName, lastName, email, mobile, passwordHash) VALUES (?, ?, ?, ?, ?)"
        val preparedStatement = connection.prepareStatement(query, Statement.RETURN_GENERATED_KEYS)
        preparedStatement.setString(1, user.firstName)
        preparedStatement.setString(2, user.lastName)
        preparedStatement.setString(3, user.email)
        preparedStatement.setString(4, user.mobile)
        preparedStatement.setString(5, user.passwordHash)
        preparedStatement.executeUpdate()
        val generatedKeys = preparedStatement.resultSet
        if (generatedKeys.next()) {
            return user.copy(id = generatedKeys.getInt(1))
        }
        throw Exception("Failed to create user")
    }

    fun findById(id: Int): User? {
        val query = "SELECT * FROM users WHERE id = ?"
        val preparedStatement = connection.prepareStatement(query)
        preparedStatement.setInt(1, id)
        val resultSet = preparedStatement.executeQuery()
        return if (resultSet.next()) {
            User(
                id = resultSet.getInt("id"),
                firstName = resultSet.getString("firstName"),
                lastName = resultSet.getString("lastName"),
                email = resultSet.getString("email"),
                mobile = resultSet.getString("mobile"),
                passwordHash = resultSet.getString("passwordHash"),
                passwordChangedAt = resultSet.getTimestamp("passwordChangedAt")?.toLocalDateTime(),
                passwordResetToken = resultSet.getString("passwordResetToken"),
                passwordResetExpires = resultSet.getTimestamp("passwordResetExpires")?.toLocalDateTime(),
                role = resultSet.getString("role"),
                isBlocked = resultSet.getBoolean("isBlocked")
            )
        } else {
            null
        }
    }

    fun findAll(): List<User> {
        val query = "SELECT * FROM users"
        val statement = connection.createStatement()
        val resultSet = statement.executeQuery(query)
        val users = mutableListOf<User>()
        while (resultSet.next()) {
            users.add(
                User(
                    id = resultSet.getInt("id"),
                    firstName = resultSet.getString("firstName"),
                    lastName = resultSet.getString("lastName"),
                    email = resultSet.getString("email"),
                    mobile = resultSet.getString("mobile"),
                    passwordHash = resultSet.getString("passwordHash"),
                    passwordChangedAt = resultSet.getTimestamp("passwordChangedAt")?.toLocalDateTime(),
                    passwordResetToken = resultSet.getString("passwordResetToken"),
                    passwordResetExpires = resultSet.getTimestamp("passwordResetExpires")?.toLocalDateTime(),
                    role = resultSet.getString("role"),
                    isBlocked = resultSet.getBoolean("isBlocked")
                )
            )
        }
        return users
    }

    fun update(user: User) {
        val query = "UPDATE users SET firstName = ?, lastName = ?, email = ?, mobile = ?, passwordHash = ?, passwordChangedAt = ?, passwordResetToken = ?, passwordResetExpires = ?, role = ?, isBlocked = ? WHERE id = ?"
        val preparedStatement = connection.prepareStatement(query)
        preparedStatement.setString(1, user.firstName)
        preparedStatement.setString(2, user.lastName)
        preparedStatement.setString(3, user.email)
        preparedStatement.setString(4, user.mobile)
        preparedStatement.setString(5, user.passwordHash)
        preparedStatement.setTimestamp(6, java.sql.Timestamp.valueOf(user.passwordChangedAt))
        preparedStatement.setString(7, user.passwordResetToken)
        preparedStatement.setTimestamp(8, java.sql.Timestamp.valueOf(user.passwordResetExpires))
        preparedStatement.setString(9, user.role)
        preparedStatement.setBoolean(10, user.isBlocked)
        preparedStatement.setInt(11, user.id)
        preparedStatement.executeUpdate()
    }

    fun delete(id: Int) {
        val query = "DELETE FROM users WHERE id = ?"
        val preparedStatement = connection.prepareStatement(query)
        preparedStatement.setInt(1, id)
        preparedStatement.executeUpdate()
    }
}
