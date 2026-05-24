# Frontend Architecture

The frontend is organized around feature modules and route metadata.

## Structure

- `frontend/src/platform`: app shell, module registry, route metadata, and frontend permission helpers.
- `frontend/src/features`: React pages, components, hooks, and feature-local services.
- `frontend/src/api`: shared HTTP client, query client, and typed API service modules.
- `frontend/src/components`: shared UI primitives and cross-feature components.
- `frontend/src/i18n`: translation loading and locale files.

Backend app packages can expose frontend modules from `backend/apps/*/web/module.tsx`. The platform registry imports those modules and turns route/menu definitions into React Router routes.

## Routing And Guards

Routes declare `requiresAuth` and optionally `requiredPermission`. `ProtectedRoute` enforces both:

- no token/user: redirect to `/login` with a safe internal redirect path
- missing permission: render access denied
- granted permission: render the route

## Auth And CSRF

- Access tokens live only in the in-memory Zustand auth store.
- Refresh tokens are backend-owned HttpOnly cookies.
- CSRF is fetched through the shared axios client and sent on state-changing API requests.
- No token should be persisted in browser storage.

## State And Data Fetching

React Query handles server state. Feature hooks keep page orchestration small, while page components primarily compose smaller UI components.

Large feature files should be split by responsibility when they grow past the agreed size envelope: page orchestration, API service, domain formatting, and display components should remain separate.
