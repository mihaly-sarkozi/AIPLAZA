# Frontend Permissions

The frontend uses role-based route permissions in `frontend/src/platform/permissions.ts`.

## Roles

- `owner`: has `*`, so every frontend permission is granted.
- `admin`: can use chat, read/train knowledge bases, and manage users.
- `user`: can use chat and read knowledge bases.

## Permission Map

- `chat.use`: `owner`, `admin`, `user`
- `knowledge.read`: `owner`, `admin`, `user`
- `knowledge.write`: `owner`, `admin`
- `knowledge.permissions.manage`: `owner`, `admin`
- `users.read`, `users.write`, `users.invite`: `owner`, `admin`
- `settings.read`: owner-only
- `chat.channel.manage`: owner-only

## Route Requirements

- `/chat`: `chat.use`
- `/chat/channel-access`: `chat.channel.manage`
- `/kb`, `/kb/create`, `/kb/edit/:uuid`, `/kb/ingest/:uuid`, `/kb/ingest/:uuid/runs/:runId`, `/onboarding/train`: `knowledge.write`
- `/admin/roles`: `users.write`
- `/admin/settings`, `/admin/forgalom`, `/admin/szamlak`, `/admin/pricing` and checkout/package admin routes: `settings.read`

`ProtectedRoute` redirects unauthenticated users to `/login` with a safe internal redirect. Authenticated users without the required permission see the shared access denied state instead of the protected page.
