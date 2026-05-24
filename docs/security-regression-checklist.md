# Security Regression Checklist

Use this checklist before security-sensitive releases.

## Auth And Session

- Access token remains in memory only.
- Refresh token remains HttpOnly cookie based.
- Login redirect accepts only safe internal paths.
- Logout clears in-memory auth state and server session.

## Browser Security

- CSRF token is attached to `POST`, `PUT`, `PATCH`, and `DELETE`.
- External links using `target="_blank"` include `rel="noopener noreferrer"`.
- User-controlled HTML is sanitized through the shared sanitizer.
- No `dangerouslySetInnerHTML` is introduced without an explicit sanitizer boundary.

## Permissions And Tenant Isolation

- Frontend route permissions match `docs/frontend-permissions.md`.
- Backend permission services enforce the same ownership/tenant boundaries.
- Owner-only frontend permissions such as `settings.read` and `chat.channel.manage` stay covered by tests.
- Cross-tenant knowledge and chat access remains denied in backend tests.

## Knowledge And Ingest

- URL ingest keeps scheme, host, IP, redirect, size, and timeout protections.
- Object storage keys remain sanitized and tenant scoped.
- Signed requests and channel credentials reject invalid or cross-tenant credentials.
- Worker/outbox retries remain idempotent and do not duplicate ingest/index data.

## Chat Persistence

- Chat history remains size-limited and user-key isolated.
- Malformed persisted JSON does not crash app startup.
- Local chat history can be cleared from the UI.
- Persisted chat content is treated as potentially sensitive content, not as auth storage.

## Error Handling

- Service-layer errors use `AppError` subclasses where available.
- HTTP responses use safe public messages and stable error codes.
- Raw exceptions, credentials, signed payloads, and tenant-private identifiers are not leaked to users.
