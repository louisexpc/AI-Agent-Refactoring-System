
package com.ecommerce.features.auth

import com.ecommerce.features.auth.models.User
import com.ecommerce.plugins.DatabaseFactory.dbQuery
import org.jetbrains.exposed.sql.*
import org.jetbrains.exposed.sql.SqlExpressionBuilder.eq
import java.time.LocalDateTime

object Users : Table() {
    val id = integer("id").autoIncrement()
    val firstName = varchar("first_name", 255)
    val lastName = varchar("last_name", 255)
    val email = varchar("email", 255)
    val mobile = varchar("mobile", 255)
    val passwordHash = varchar("password_hash", 255)
    val role = varchar("role", 50).default("user")
    val isBlocked = bool("is_blocked").default(false)
    val passwordChangedAt = datetime("password_changed_at").nullable()
    val passwordResetToken = varchar("password_reset_token", 255).nullable()
    val passwordResetExpires = datetime("password_reset_expires").nullable()

    override val primaryKey = PrimaryKey(id)
}

class UserRepository {

    suspend fun createUser(user: User): User = dbQuery {
        val statement = Users.insert {
            it[firstName] = user.firstName
            it[lastName] = user.lastName
            it[email] = user.email
            it[mobile] = user.mobile
            it[passwordHash] = user.passwordHash
            it[role] = user.role
        }
        statement.resultedValues?.first()?.toUser()!!
    }

    suspend fun getUserByEmail(email: String): User? = dbQuery {
        Users.select { Users.email eq email }
            .map { it.toUser() }
            .singleOrNull()
    }

    suspend fun getUserById(id: Int): User? = dbQuery {
        Users.select { Users.id eq id }
            .map { it.toUser() }
            .singleOrNull()
    }

    suspend fun updateUser(id: Int, user: User): User = dbQuery {
        Users.update({ Users.id eq id }) {
            it[firstName] = user.firstName
            it[lastName] = user.lastName
            it[mobile] = user.mobile
        }
        getUserById(id)!!
    }

    suspend fun deleteUser(id: Int): Unit = dbQuery {
        Users.deleteWhere { Users.id eq id }
    }

    private fun ResultRow.toUser() = User(
        id = this[Users.id],
        firstName = this[Users.firstName],
        lastName = this[Users.lastName],
        email = this[Users.email],
        mobile = this[Users.mobile],
        passwordHash = this[Users.passwordHash],
        role = this[Users.role],
        isBlocked = this[Users.isBlocked],
        passwordChangedAt = this[Users.passwordChangedAt],
        passwordResetToken = this[Users.passwordResetToken],
        passwordResetExpires = this[Users.passwordResetExpires]
    )
}
