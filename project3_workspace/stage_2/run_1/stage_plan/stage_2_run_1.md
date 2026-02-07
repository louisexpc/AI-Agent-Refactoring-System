# Stage 2: Authentication & Users Refactoring Plan

This plan outlines the steps to refactor the Node.js authentication and user management features to a Kotlin backend using Ktor.

## 1. Data Classes

- **User.kt**: Create a data class `User` that mirrors the schema of the `users` table. This will be the core model for our authentication and user features.
- **Request/Response Models**: Define data classes for handling API requests and responses. This includes:
    - `UserRegistrationRequest`
    - `UserLoginRequest`
    - `UserLoginResponse` (including tokens)
    - `UserProfileUpdateRequest`
    - `UserProfileResponse`

File Location: `src/main/kotlin/com/ecommerce/features/auth/models/`

## 2. Repository Layer

- **UserRepository.kt**: This repository will handle all database interactions related to users. It will use raw SQL queries to perform CRUD operations.
    - `createUser(user: User): User`
    - `getUserByEmail(email: String): User?`
    - `getUserById(id: Int): User?`
    - `updateUser(id: Int, user: User): User`
    - `deleteUser(id: Int)`

File Location: `src/main/kotlin/com/ecommerce/features/auth/`

## 3. Service Layer

- **AuthService.kt**: This service will contain the business logic for authentication.
    - User registration (hashing passwords)
    - User login (verifying credentials, generating JWTs)
    - Password reset logic (if applicable)
- **UserService.kt**: This service will manage user profile data.
    - Retrieving user profiles
    - Updating user information
    - Deleting user accounts

File Location: `src/main/kotlin/com/ecommerce/features/auth/`

## 4. Routing

- **AuthRoutes.kt**: Defines the public-facing authentication endpoints.
    - `POST /api/auth/register`
    - `POST /api/auth/login`
    - `POST /api/auth/refresh` (for refreshing JWTs)
- **UserRoutes.kt**: Defines the protected endpoints for user management.
    - `GET /api/users/{id}`
    - `PUT /api/users/{id}`
    - `DELETE /api/users/{id}`

File Location: `src/main/kotlin/com/ecommerce/features/auth/`

## 5. Security

- **Security.kt**: This file will configure Ktor's security features.
    - Configure JWT authentication provider.
    - Define validation logic for incoming JWTs.
    - Implement role-based authorization to protect routes.

File Location: `src/main/kotlin/com/ecommerce/plugins/`
