package com.ecommerce.repository

import com.ecommerce.models.Blog
import java.sql.Connection

class BlogRepository(private val connection: Connection) {

    fun createBlog(blog: Blog): Blog {
        val statement = connection.prepareStatement("INSERT INTO blogs (title, description, category, author, images) VALUES (?, ?, ?, ?, ?)", java.sql.Statement.RETURN_GENERATED_KEYS)
        statement.setString(1, blog.title)
        statement.setString(2, blog.description)
        statement.setString(3, blog.category)
        statement.setString(4, blog.author)
        statement.setArray(5, connection.createArrayOf("text", blog.images.toTypedArray()))
        statement.executeUpdate()
        val generatedKeys = statement.generatedKeys
        if (generatedKeys.next()) {
            blog.id = generatedKeys.getInt(1)
        }
        return blog
    }

    fun updateBlog(id: Int, blog: Blog): Blog? {
        val statement = connection.prepareStatement("UPDATE blogs SET title = ?, description = ?, category = ?, author = ?, images = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?")
        statement.setString(1, blog.title)
        statement.setString(2, blog.description)
        statement.setString(3, blog.category)
        statement.setString(4, blog.author)
        statement.setArray(5, connection.createArrayOf("text", blog.images.toTypedArray()))
        statement.setInt(6, id)
        val updatedRows = statement.executeUpdate()
        return if (updatedRows > 0) getBlogById(id) else null
    }

    fun getBlogById(id: Int): Blog? {
        val statement = connection.prepareStatement("SELECT * FROM blogs WHERE id = ?")
        statement.setInt(1, id)
        val resultSet = statement.executeQuery()
        return if (resultSet.next()) {
            Blog(
                id = resultSet.getInt("id"),
                title = resultSet.getString("title"),
                description = resultSet.getString("description"),
                category = resultSet.getString("category"),
                numViews = resultSet.getInt("num_views"),
                author = resultSet.getString("author"),
                images = (resultSet.getArray("images").array as Array<String>).toList()
            )
        } else {
            null
        }
    }

    fun getAllBlogs(): List<Blog> {
        val statement = connection.prepareStatement("SELECT * FROM blogs")
        val resultSet = statement.executeQuery()
        val blogs = mutableListOf<Blog>()
        while (resultSet.next()) {
            blogs.add(
                Blog(
                    id = resultSet.getInt("id"),
                    title = resultSet.getString("title"),
                    description = resultSet.getString("description"),
                    category = resultSet.getString("category"),
                    numViews = resultSet.getInt("num_views"),
                    author = resultSet.getString("author"),
                    images = (resultSet.getArray("images").array as Array<String>).toList()
                )
            )
        }
        return blogs
    }

    fun deleteBlog(id: Int): Boolean {
        val statement = connection.prepareStatement("DELETE FROM blogs WHERE id = ?")
        statement.setInt(1, id)
        return statement.executeUpdate() > 0
    }

    fun likeBlog(blogId: Int, userId: Int): Blog? {
        val insertStatement = connection.prepareStatement("INSERT INTO blog_likes (blog_id, user_id) VALUES (?, ?) ON CONFLICT DO NOTHING")
        insertStatement.setInt(1, blogId)
        insertStatement.setInt(2, userId)
        insertStatement.executeUpdate()
        return getBlogById(blogId)
    }

    fun dislikeBlog(blogId: Int, userId: Int): Blog? {
        val deleteStatement = connection.prepareStatement("DELETE FROM blog_likes WHERE blog_id = ? AND user_id = ?")
        deleteStatement.setInt(1, blogId)
        deleteStatement.setInt(2, userId)
        deleteStatement.executeUpdate()
        return getBlogById(blogId)
    }
}
