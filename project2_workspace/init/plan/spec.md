# Refactoring Specification

## 1. System Topography
The original system is a monolithic Ruby on Rails application. It follows a standard MVC pattern, with business logic concentrated in the controllers and models, and the UI rendered through server-side ERB/HAML templates. The application is a CRM system with core entities like Accounts, Contacts, Leads, and Opportunities. User management and authentication are handled by the Devise gem. The database schema is well-defined in `db/schema.rb`.

## 2. Module Cluster Map
The refactoring will split the monolith into a Go backend and a React frontend.

*   **Backend (Go/Gin)**:
    *   **Models**: `app/models/**/*.rb` -> `backend/internal/models/*.go`
    *   **Controllers**: `app/controllers/**/*.rb` -> `backend/internal/handlers/*.go`
    *   **Routes**: `config/routes.rb` -> `backend/cmd/server/main.go` (Gin router setup)
*   **Frontend (React/TypeScript)**:
    *   **Views**: `app/views/**/*.html.haml` -> `frontend/src/pages/**/*.tsx` and `frontend/src/components/**/*.tsx`
    *   **Assets**: `app/assets/` -> `frontend/src/` (to be managed by Vite/Webpack)

## 3. Staging Roadmap

### Stage 1: Backend - Core Models & Database Layer
*   **Rationale**: This stage establishes the foundation for the backend by defining the data structures and database connectivity. It's a prerequisite for any business logic implementation.
*   **Interface Points**: Go structs corresponding to the Rails models.
*   **Included Files**:
    *   `app/models/entities/account.rb`
    *   `app/models/entities/contact.rb`
    *   `app/models/entities/opportunity.rb`
    *   `app/models/entities/lead.rb`
    *   `app/models/entities/campaign.rb`
    *   `app/models/users/user.rb`
    *   `db/schema.rb`

### Stage 2: Backend - API Implementation (Users & Auth)
*   **Rationale**: This stage implements the critical user management and authentication functionality, which is a prerequisite for most other features.
*   **Interface Points**: RESTful API endpoints for user registration, login, and profile management.
*   **Included Files**:
    *   `app/controllers/users_controller.rb`
    *   `app/controllers/registrations_controller.rb`
    *   `app/controllers/sessions_controller.rb`
    *   `app/controllers/passwords_controller.rb`
    *   `config/routes.rb` (auth-related routes)

### Stage 3: Backend - API Implementation (Core CRM)
*   **Rationale**: This stage implements the core business logic of the CRM application.
*   **Interface Points**: RESTful API endpoints for CRUD operations on Accounts, Contacts, Opportunities, Leads, and Campaigns.
*   **Included Files**:
    *   `app/controllers/entities/accounts_controller.rb`
    *   `app/controllers/entities/contacts_controller.rb`
    *   `app/controllers/entities/opportunities_controller.rb`
    *   `app/controllers/entities/leads_controller.rb`
    *   `app/controllers/entities/campaigns_controller.rb`
    *   `config/routes.rb` (CRM-related routes)

### Stage 4: Frontend - Project Setup & Core Components
*   **Rationale**: This stage sets up the frontend project and creates the reusable UI components that will be used across the application.
*   **Interface Points**: React components for common UI elements (buttons, forms, tables, etc.).
*   **Included Files**:
    *   `app/assets/`
    *   `app/views/layouts/`

### Stage 5: Frontend - User & Auth Pages
*   **Rationale**: This stage creates the user-facing pages for authentication and profile management, connecting to the backend APIs built in Stage 2.
*   **Interface Points**: React pages for login, registration, and user profile.
*   **Included Files**:
    *   `app/views/devise/`
    *   `app/views/users/`

### Stage 6: Frontend - Core CRM Pages
*   **Rationale**: This stage builds the main pages of the CRM application, allowing users to interact with the core entities.
*   **Interface Points**: React pages for listing, creating, editing, and viewing Accounts, Contacts, Opportunities, Leads, and Campaigns.
*   **Included Files**:
    *   `app/views/accounts/`
    *   `app/views/contacts/`
    *   `app/views/opportunities/`
    *   `app/views/leads/`
    *   `app/views/campaigns/`

### Stage 7: Dockerization
*   **Rationale**: This final stage packages the backend and frontend services for easy deployment and development.
*   **Interface Points**: `Dockerfile` for backend and frontend, and a `docker-compose.yml` to orchestrate them.
*   **Included Files**:
    *   `Dockerfile` (from original repo, to be adapted)
    *   `docker-compose.yml` (from original repo, to be adapted)

## 4. Execution Risks
*   **Circular Dependencies**: The split between backend and frontend should minimize circular dependencies, but care must be taken to ensure that the API contract is well-defined and stable.
*   **State Management**: The React frontend will require a robust state management solution (e.g., Redux, MobX, or React Context) to handle the application's state, which was previously managed on the server-side by Rails.
*   **Authentication**: The authentication logic will need to be carefully migrated from Devise to a token-based approach (e.g., JWT) for the stateless API.
