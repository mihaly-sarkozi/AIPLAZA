# Frontend Chat Persistence

Chat persistence is handled by `frontend/src/features/chat/services/chatPersistenceService.ts`.

## Storage Policy

- Auth tokens are never stored in `localStorage`, `sessionStorage`, or IndexedDB.
- Chat history is not an auth secret, but it can contain sensitive user content.
- Persisted chat state is keyed per user with `aiplaza_chat_persist_v2:<userId>`.
- Legacy `sessionStorage` data under `aiplaza_chat_session_v1:<userId>` is migrated once and removed.
- Context notice fallback uses `aiplaza_chat_context_notice`.

## Limits And Sanitization

- At most `100` messages are persisted.
- Persisted text is capped at `100000` characters across the session payload.
- Malformed JSON returns `null` instead of crashing the app.
- Message fields are sanitized before save/load; unsupported fields are dropped.
- `actionHref` is only restored when it starts with `/`.
- `progressPercent` is clamped to `0..100`.

## User Controls

The chat UI exposes local history clearing through the new-chat/clear action. Clearing removes the current user's persisted chat key, legacy session key, and context notice.
