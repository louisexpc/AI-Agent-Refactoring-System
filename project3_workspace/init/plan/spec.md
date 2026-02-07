# Refactoring Specification

## 1. System Topography
The original system is a monolithic Node.js application using the Express.js framework and MongoDB with Mongoose. The codebase is organized by technical layers (`controllers`, `models`, `routes`), which leads to low cohesion and high coupling. The goal is to refactor this into a Kotlin application with a vertical slicing architecture, grouping code by features/domains.

## 2. Module Cluster Map
The following clusters have been identified:

*   **Foundation**: Database, routing, and core application setup.
*   **Authentication**: User registration, login, logout, and JWT management.
*   **Users**: User profile management.
*   **Products**: Product and category management.
*   **Carts**: Shopping cart functionality.
*   **Orders**: Checkout and order history.
*   **Coupons**: Coupon and discount management.
*   **Blogs**: Blog posts and related functionality.
*   **Search**: Product search functionality.

## 3. Staging Roadmap

### Stage 1: Foundation
*   **Rationale**: Establish the database schema and basic application structure. This is the foundation upon which all other features will be built.
*   **Interface Points**: Database connection pool, basic routing setup.
*   **Included Files**:
    *   `dbconn.js`
    *   `index.js`
    *   `middlewares/errorHandler.js`
    *   `utils/validateObjectId.js`

### Stage 2: Authentication & Users
*   **Rationale**: Implement user authentication and management, which is a core feature required by many other parts of the application.
*   **Interface Points**: JWT generation and validation, user creation and retrieval.
*   **Included Files**:
    *   `controllers/userController.js`
    *   `models/userModel.js`
    *   `routes/authRoute.js`
    *   `routes/userRouter.js`
    *   `middlewares/authorizationMiddleware.js`
    *   `jwtToken.js`
    *   `refreshToken.js`

### Stage 3: Products & Categories
*   **Rationale**: Implement the core e-commerce functionality of managing products and categories.
*   **Interface Points**: Product and category CRUD operations.
*   **Included Files**:
    *   `controllers/productController.js`
    *   `controllers/categoryController.js`
    *   `models/productModel.js`
    *   `models/categoryModel.js`
    *   `routes/productRouter.js`
    *   `routes/categoryRouters.js`

### Stage 4: Carts
*   **Rationale**: Implement the shopping cart feature.
*   **Interface Points**: Add, remove, and update items in the cart.
*   **Included Files**:
    *   `controllers/cartController.js`
    *   `models/cartModel.js`
    *   `routes/cartRouter.js`

### Stage 5: Orders
*   **Rationale**: Implement the checkout and order management functionality.
*   **Interface Points**: Order creation and retrieval.
*   **Included Files**:
    *   `controllers/orderController.js`
    *   `models/orderModel.js`
    *   `routes/orderRoute.js`

### Stage 6: Coupons
*   **Rationale**: Implement the coupon and discount functionality.
*   **Interface Points**: Coupon creation, validation, and application.
*   **Included Files**:
    *   `controllers/couponController.js`
    *   `models/couponModel.js`
    *   `routes/couponRouter.js`

### Stage 7: Blogs
*   **Rationale**: Implement the blog functionality.
*   **Interface Points**: Blog post CRUD operations.
*   **Included Files**:
    *   `controllers/blogController.js`
    *   `models/blogModel.js`
    *   `routes/blogRouter.js`

### Stage 8: Search
*   **Rationale**: Implement product search functionality.
*   **Interface Points**: Search endpoint.
*   **Included Files**:
    *   `controllers/searchController.js`
    *   `routes/searchRouter.js`
    *   `utils/elasticSearchClient.js`
    *   `utils/indexProducts.js`
    *   `utils/createProductIndex.js`

## 4. Execution Risks
*   **Circular Dependencies**: The original code has some tight coupling between modules. The staging plan is designed to minimize this, but some refactoring may be required to break cycles.
*   **Database Migration**: The migration from MongoDB to PostgreSQL requires a careful mapping of data types and relationships. The proposed schema should be validated and tested thoroughly.
*   **RAW SQL**: The requirement to use raw SQL increases the risk of SQL injection vulnerabilities. All queries must be parameterized and validated.
