# Stage 1: Backend - Core Models & Database Layer

This stage focuses on translating the Ruby on Rails models into Go structs. It also involves setting up the database connection and basic data access layer (DAL) functions.

**Tasks:**

1.  Create Go structs for the following models:
    *   Account
    *   Contact
    *   Opportunity
    *   Lead
    *   Campaign
    *   User
2.  The structs should be placed in `backend/internal/models/`.
3.  Set up a database connection using the `database/sql` package and a suitable driver (e.g., `pq` for PostgreSQL).
4.  Create a `main.go` file in `backend/cmd/server/` to initialize the database connection.
