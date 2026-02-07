# Stage 3: Products & Categories Refactoring Plan

This plan outlines the steps to refactor the product and category management features from Node.js to Kotlin.

1.  **Data Classes**:
    *   Create `Product.kt` in `src/main/kotlin/com/ecommerce/features/products/models` to represent the `Product` data model.
    *   Create `Category.kt` in `src/main/kotlin/com/ecommerce/features/products/models` to represent the `Category` data model.
    *   Define request and response data classes for both product and category operations within their respective model files.

2.  **Repositories**:
    *   Create `ProductRepository.kt` in `src/main/kotlin/com/ecommerce/features/products` to handle database interactions for products using raw SQL.
    *   Create `CategoryRepository.kt` in `src/main/kotlin/com/ecommerce/features/products` to handle database interactions for categories using raw SQL.

3.  **Services**:
    *   Create `ProductService.kt` in `src/main/kotlin/com/ecommerce/features/products` to contain the business logic for product operations.
    *   Create `CategoryService.kt` in `src/main/kotlin/com/ecommerce/features/products` to contain the business logic for category operations.

4.  **Routes**:
    *   Create `ProductRoutes.kt` in `src/main/kotlin/com/ecommerce/features/products` to define the API endpoints for product CRUD operations.
    *   Create `CategoryRoutes.kt` in `src/main/kotlin/com/ecommerce/features/products` to define the API endpoints for category CRUD operations.
