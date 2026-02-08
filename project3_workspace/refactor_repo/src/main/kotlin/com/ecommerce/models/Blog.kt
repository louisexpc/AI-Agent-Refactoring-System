package com.ecommerce.models

import org.jetbrains.exposed.sql.*
import org.jetbrains.exposed.sql.javatime.datetime
import java.time.LocalDateTime

data class Blog(
    val id: Int,
    val title: String,
    val content: String,
    val category: String,
    val numViews: Int,
    val numLikes: Int,
    val image: String,
    val author: String,
    val createdAt: LocalDateTime,
    val updatedAt: LocalDateTime
)

object Blogs : Table() {
    val id = integer("id").autoIncrement()
    val title = varchar("title", 255)
    val content = text("content")
    val category = varchar("category", 255)
    val numViews = integer("num_views").default(0)
    val numLikes = integer("num_likes").default(0)
    val image = varchar("image", 255).default("https://ibb.co/2sY9nwj")
    val author = varchar("author", 255).default("Admin")
    val createdAt = datetime("created_at").default(LocalDateTime.now())
    val updatedAt = datetime("updated_at").default(LocalDateTime.now())

    override val primaryKey = PrimaryKey(id)
}
