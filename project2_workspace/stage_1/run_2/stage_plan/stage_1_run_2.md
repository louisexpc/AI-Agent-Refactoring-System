# Stage 1, Run 2: Backend - Core Models & Database Layer

## 1. Goal
Refactor the Rails models into Go structs and establish a database connection.

## 2. Plan

1.  **Create Go struct files:**
    *   `Account` -> `/workspace/refactor_repo/backend/internal/models/account.go`
    *   `Contact` -> `/workspace/refactor_repo/backend/internal/models/contact.go`
    *   `Opportunity` -> `/workspace/refactor_repo/backend/internal/models/opportunity.go`
    *   `Lead` -> `/workspace/refactor_repo/backend/internal/models/lead.go`
    *   `Campaign` -> `/workspace/refactor_repo/backend/internal/models/campaign.go`
    *   `User` -> `/workspace/refactor_repo/backend/internal/models/user.go`

2.  **Create database connection:**
    *   Create `/workspace/refactor_repo/backend/internal/database/database.go` to manage the database connection.

3.  **Create main application file:**
    *   Create `/workspace/refactor_repo/backend/cmd/server/main.go` to initialize the database and start the server (in future stages).

## 3. Rationale
This stage builds the data structure foundation for the Go backend. By creating the Go structs and the database connection first, we can ensure that the subsequent stages have a stable base to build upon.
