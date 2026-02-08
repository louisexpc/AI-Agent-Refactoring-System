package com.example.ecommerce

import com.zaxxer.hikari.HikariConfig
import com.zaxxer.hikari.HikariDataSource
import org.jetbrains.exposed.sql.Database
import org.jetbrains.exposed.sql.transactions.transaction
import org.jetbrains.exposed.sql.SchemaUtils
import org.jetbrains.exposed.sql.Table
import org.jetbrains.exposed.sql.javatime.datetime

object Users : Table() {
    val id = integer("id").autoIncrement()
    val username = varchar("username", 255).uniqueIndex()
    val password = varchar("password", 255)
    val email = varchar("email", 255).uniqueIndex()
    val createdAt = datetime("created_at")
    override val primaryKey = PrimaryKey(id)
}

object Products : Table() {
    val id = integer("id").autoIncrement()
    val name = varchar("name", 255)
    val description = text("description").nullable()
    val price = decimal("price", 10, 2)
    val stock = integer("stock")
    val createdAt = datetime("created_at")
    override val primaryKey = PrimaryKey(id)
}

object Orders : Table() {
    val id = integer("id").autoIncrement()
    val userId = integer("user_id").references(Users.id)
    val status = varchar("status", 50)
    val totalAmount = decimal("total_amount", 10, 2)
    val createdAt = datetime("created_at")
    override val primaryKey = PrimaryKey(id)
}

object OrderItems : Table() {
    val id = integer("id").autoIncrement()
    val orderId = integer("order_id").references(Orders.id)
    val productId = integer("product_id").references(Products.id)
    val quantity = integer("quantity")
    val price = decimal("price", 10, 2)
    override val primaryKey = PrimaryKey(id)
}

fun initDatabase() {
    val config = HikariConfig().apply {
        jdbcUrl = "jdbc:postgresql://localhost:5432/ecommerce"
        driverClassName = "org.postgresql.Driver"
        username = "user"
        password = "password"
        maximumPoolSize = 10
    }
    val dataSource = HikariDataSource(config)
    Database.connect(dataSource)

    transaction {
        SchemaUtils.create(Users, Products, Orders, OrderItems)
    }
}
