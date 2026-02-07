
package com.ecommerce.plugins

import com.zaxxer.hikari.HikariConfig
import com.zaxxer.hikari.HikariDataSource
import io.ktor.server.application.*
import org.flywaydb.core.Flyway
import java.sql.Connection

object Database {
    private var dataSource: HikariDataSource? = null

    fun init(application: Application) {
        val config = application.environment.config
        val hikariConfig = HikariConfig().apply {
            jdbcUrl = config.property("database.jdbcUrl").getString()
            driverClassName = config.property("database.driverClassName").getString()
            username = config.property("database.username").getString()
            password = config.property("database.password").getString()
            maximumPoolSize = config.property("database.maximumPoolSize").getString().toInt()
            isAutoCommit = false
            transactionIsolation = "TRANSACTION_REPEATABLE_READ"
            validate()
        }
        dataSource = HikariDataSource(hikariConfig)
        runMigrations()
    }

    private fun runMigrations() {
        val flyway = Flyway.configure().dataSource(dataSource).load()
        flyway.migrate()
    }

    val connection: Connection
        get() = dataSource!!.connection
}
