# Stage 6: Admin & Utility APIs (Run 2)

## Rationale

This stage implements the remaining admin and utility features. This is the second run of this stage, to fix the mapping file.

## Plan

1.  **Admin Controller**: Create an `AdminController` that exposes REST endpoints for admin-specific functionality.
2.  **Email Controller**: Create an `EmailController` that exposes a REST endpoint for sending emails.
3.  **Search Controller**: Create a `SearchController` that exposes a REST endpoint for searching products.
4.  **Routes**: Create routes for admin, email, and search APIs.

## SQL Query Checklist

*   **Users**:
    *   `UPDATE users SET isBlocked = ? WHERE id = ?`
