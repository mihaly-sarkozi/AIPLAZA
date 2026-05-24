# Frontend Testing

## Commands

Run unit and component tests:

```bash
cd frontend
pnpm test
```

Run lint and production build:

```bash
cd frontend
pnpm lint
pnpm build
```

Run Playwright smoke tests:

```bash
cd frontend
pnpm test:e2e
```

Install the browser runtime when needed:

```bash
cd frontend
pnpm exec playwright install chromium
```

## Coverage Focus

- Vitest and Testing Library cover helpers, permission guards, chat persistence, and key UI components.
- Component tests currently cover `ChatComposer`, `ChatMessagesList`, `IngestRunProgress`, and `ProtectedRoute`.
- Playwright smoke tests cover login render, protected route redirect, authenticated KB/chat render, permission denied, and platform-admin login render with mocked API responses.

## Test Boundaries

- `pnpm test` excludes `e2e/**`; Playwright specs are run only by `pnpm test:e2e`.
- Playwright tests mock backend API calls so smoke coverage can run without a live backend.
- Access tokens remain in memory only. E2E auth is simulated through the same refresh flow the app uses at runtime.
