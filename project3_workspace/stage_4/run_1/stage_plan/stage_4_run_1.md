# Stage 4: Carts Refactoring Plan

## 1. Data Classes

*   Create `Cart.kt` in `src/main/kotlin/com/ecommerce/features/cart/models` to define the `Cart` data class.
*   Create `CartItem.kt` in `src/main/kotlin/com/ecommerce/features/cart/models` to define the `CartItem` data class.
*   Create `CartRequest.kt` and `CartResponse.kt` in `src/main/kotlin/com/ecommerce/features/cart/models` for handling API requests and responses.

## 2. Repository

*   Create `CartRepository.kt` in `src/main/kotlin/com/ecommerce/features/cart`.
*   Implement functions for CRUD operations on carts and cart items using raw SQL.

## 3. Service

*   Create `CartService.kt` in `src/main/kotlin/com/ecommerce/features/cart`.
*   Implement the business logic for cart management, including adding/removing items and calculating totals.

## 4. Routes

*   Create `CartRoutes.kt` in `src/main/kotlin/com/ecommerce/features/cart`.
*   Define the Ktor routes for all cart-related operations.
