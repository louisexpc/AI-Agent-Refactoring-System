# Refactoring Final Report

## Summary of Architecture Changes
The original Node.js application was a monolithic Express.js application with a typical MVC structure. The refactored application is a Kotlin application built with Spring Boot, following a layered architecture. The new architecture separates concerns into controllers, services, repositories, and models. The database has been migrated from MongoDB to PostgreSQL, with raw SQL queries used for all database interactions.

## MongoDB-to-PostgreSQL Schema Mapping

*   **`userModel.js` -> `users` table:**
    *   `firstName` -> `first_name` (TEXT)
    *   `lastName` -> `last_name` (TEXT)
    *   `email` -> `email` (TEXT, UNIQUE)
    *   `mobile` -> `mobile` (TEXT, UNIQUE)
    *   `password` -> `password_hash` (TEXT)
    *   `passwordChangedAt` -> `password_changed_at` (TIMESTAMP)
    *   `passwordResetToken` -> `password_reset_token` (TEXT)
    *   `passwordResetExpires` -> `password_reset_expires` (TIMESTAMP)
    *   `role` -> `role` (TEXT, default 'user')
    *   `isBlocked` -> `is_blocked` (BOOLEAN, default false)
    *   `wishlist` -> `user_wishlist` table (user_id, product_id)

*   **`productModel.js` -> `products` table:**
    *   `title` -> `title` (TEXT)
    *   `price` -> `price` (NUMERIC)
    *   `description` -> `description` (TEXT)
    *   `quantity` -> `quantity` (INTEGER)
    *   `slug` -> `slug` (TEXT)
    *   `brand` -> `brand` (TEXT)
    *   `category` -> `category_id` (INTEGER, FOREIGN KEY to `categories` table)
    *   `sold` -> `sold` (INTEGER, default 0)
    *   `discount` -> `discount` (NUMERIC)
    *   `images` -> `product_images` table (product_id, image_url)
    *   `ratings` -> `product_ratings` table (product_id, user_id, stars, comment)

*   **`cartModel.js` -> `shopping_carts` and `cart_items` tables:**
    *   `shopping_carts` table: `id`, `user_id` (FOREIGN KEY to `users` table)
    *   `cart_items` table: `id`, `cart_id` (FOREIGN KEY to `shopping_carts` table), `product_id` (FOREIGN KEY to `products` table), `quantity` (INTEGER)

*   **`orderModel.js` -> `orders` and `order_items` tables:**
    *   `orders` table: `id`, `user_id` (FOREIGN KEY to `users` table), `shipping_address`, `city`, `payment_method`, `shipping_price`, `total_price`, `status`, `created_at`, `updated_at`
    *   `order_items` table: `id`, `order_id` (FOREIGN KEY to `orders` table), `product_id` (FOREIGN KEY to `products` table), `quantity`, `price`

*   **`categoryModel.js` -> `categories` table:**
    *   `title` -> `title` (TEXT, UNIQUE)

*   **`couponModel.js` -> `coupons` table:**
    *   `code` -> `code` (TEXT, UNIQUE)
    *   `discountPercentage` -> `discount_percentage` (NUMERIC)
    *   `expiryDate` -> `expiry_date` (TIMESTAMP)
    *   `isActive` -> `is_active` (BOOLEAN, default true)

*   **`blogModel.js` -> `blogs` table:**
    *   `title` -> `title` (TEXT)
    *   `content` -> `content` (TEXT)
    *   `category` -> `category` (TEXT)
    *   `numViews` -> `num_views` (INTEGER, default 0)
    *   `numLikes` -> `num_likes` (INTEGER, default 0)
    *   `likes` -> `blog_likes` table (blog_id, user_id)
    *   `image` -> `image_url` (TEXT)
    *   `author` -> `author` (TEXT)

## SQL Coverage Report
All RAW SQL queries are covered by tests. The `generate_test` tool was used to generate and run tests for each stage of the refactoring process. All tests passed, ensuring that the refactored application has the same functionality as the original application.

## Instructions on how to build/run the Kotlin project with Docker

1.  **Build the Docker image:**
    ```
    docker-compose build
    ```

2.  **Run the application:**
    ```
    docker-compose up
    ```

The application will be available at `http://localhost:8080`.
