# SQL Coverage Report

This report summarizes the SQL queries implemented in the refactored Kotlin application and their test coverage.

## Stage 1: Foundation - Database, Users, Products, and Categories

*   **Users**:
    *   `CREATE TABLE users`: Covered by tests in Stage 1.
    *   `INSERT INTO users`: Covered by tests in Stage 1.
    *   `SELECT * FROM users`: Covered by tests in Stage 1.
    *   `SELECT * FROM users WHERE id = ?`: Covered by tests in Stage 1.
    *   `UPDATE users SET ... WHERE id = ?`: Covered by tests in Stage 1.
    *   `DELETE FROM users WHERE id = ?`: Covered by tests in Stage 1.
*   **Products**:
    *   `CREATE TABLE products`: Covered by tests in Stage 1.
    *   `INSERT INTO products`: Covered by tests in Stage 1.
    *   `SELECT * FROM products`: Covered by tests in Stage 1.
    *   `SELECT * FROM products WHERE id = ?`: Covered by tests in Stage 1.
    *   `UPDATE products SET ... WHERE id = ?`: Covered by tests in Stage 1.
    *   `DELETE FROM products WHERE id = ?`: Covered by tests in Stage 1.
*   **Categories**:
    *   `CREATE TABLE categories`: Covered by tests in Stage 1.
    *   `INSERT INTO categories`: Covered by tests in Stage 1.
    *   `SELECT * FROM categories`: Covered by tests in Stage 1.
    *   `SELECT * FROM categories WHERE id = ?`: Covered by tests in Stage 1.
    *   `UPDATE categories SET ... WHERE id = ?`: Covered by tests in Stage 1.
    *   `DELETE FROM categories WHERE id = ?`: Covered by tests in Stage 1.

## Stage 2: Authentication & Authorization

*   **Users**:
    *   `SELECT * FROM users WHERE email = ?`: Covered by tests in Stage 2.
    *   `INSERT INTO users (firstName, lastName, email, mobile, password) VALUES (?, ?, ?, ?, ?)`: Covered by tests in Stage 2.

## Stage 3: Product & Category APIs

*   All SQL queries for Products and Categories are covered by tests in Stage 1 and Stage 3.

## Stage 4: Cart & Order APIs

*   **Carts**:
    *   `CREATE TABLE carts`: Covered by tests in Stage 4.
    *   `CREATE TABLE cart_items`: Covered by tests in Stage 4.
    *   `SELECT * FROM carts WHERE user_id = ?`: Covered by tests in Stage 4.
    *   `INSERT INTO carts (user_id) VALUES (?)`: Covered by tests in Stage 4.
    *   `INSERT INTO cart_items (cart_id, product_id, qty) VALUES (?, ?, ?)`: Covered by tests in Stage 4.
    *   `UPDATE cart_items SET qty = ? WHERE cart_id = ? AND product_id = ?`: Covered by tests in Stage 4.
    *   `DELETE FROM cart_items WHERE cart_id = ?`: Covered by tests in Stage 4.
*   **Orders**:
    *   `CREATE TABLE orders`: Covered by tests in Stage 4.
    *   `CREATE TABLE order_items`: Covered by tests in Stage 4.
    *   `INSERT INTO orders (...) VALUES (...)`: Covered by tests in Stage 4.
    *   `INSERT INTO order_items (...) VALUES (...)`: Covered by tests in Stage 4.

## Stage 5: Blog & Coupon APIs

*   **Blogs**:
    *   `CREATE TABLE blogs`: Covered by tests in Stage 5.
    *   `SELECT * FROM blogs`: Covered by tests in Stage 5.
    *   `SELECT * FROM blogs WHERE id = ?`: Covered by tests in Stage 5.
    *   `INSERT INTO blogs (...) VALUES (...)`: Covered by tests in Stage 5.
    *   `UPDATE blogs SET ... WHERE id = ?`: Covered by tests in Stage 5.
    *   `DELETE FROM blogs WHERE id = ?`: Covered by tests in Stage 5.
*   **Coupons**:
    *   `CREATE TABLE coupons`: Covered by tests in Stage 5.
    *   `SELECT * FROM coupons`: Covered by tests in Stage 5.
    *   `SELECT * FROM coupons WHERE id = ?`: Covered by tests in Stage 5.
    *   `INSERT INTO coupons (...) VALUES (...)`: Covered by tests in Stage 5.
    *   `UPDATE coupons SET ... WHERE id = ?`: Covered by tests in Stage 5.
    *   `DELETE FROM coupons WHERE id = ?`: Covered by tests in Stage 5.

## Stage 6: Admin & Utility APIs

*   **Users**:
    *   `UPDATE users SET isBlocked = ? WHERE id = ?`: Covered by tests in Stage 6.

**Conclusion**: All RAW SQL queries are covered by tests.
