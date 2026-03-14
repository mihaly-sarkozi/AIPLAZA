# Technical refactor map (module-by-module)

Realistic assessment: strengths, risks, and recommended next refactors. Not a full rewrite plan.

---

## config

**Strengths:** Centralized settings (Dev/Prod), `.env` loading in one place, `load_settings()` cached. Clear separation from app code.

**Risks:** `config/loader.py` references `DevConfig`/`ProdConfig` from `.dev`/`.prod`; ensure all required vars are documented (e.g. in `.env.example`). No validation layer for required vs optional.

**Recommended next:** Document required env vars in one place; add a small validation step at startup (e.g. fail fast if `DATABASE_URL` missing in prod).

---

## main.py

**Strengths:** Single entry point; middleware order explicit; lifespan for DB warm-up; routers under `/api`; rate limit and CORS configured.

**Risks:** No `create_app()` factory yet (tests use lazy `get_app()` which imports main). Duplicate `import logging`/`os` at top. Large file; could split middleware registration into a helper.

**Recommended next:** Extract `create_app()` returning FastAPI instance; call it from `main` and from tests. Remove duplicate imports. Optional: move middleware registration into `app/core/app_factory.py` or keep in main with clear sections.

---

## apps/core

**Strengths:** DI container (`AppContainer`) centralizes dependencies; session factory, security (token, allowlist, logger), Qdrant, email, auth/user/settings/audit/chat/knowledge services. Middleware: tenant, auth, CSRF, correlation_id, timing, rate limit. DB session dependency; Redis/cache abstractions.

**Risks:** Container is a big god object; any new service requires editing it. Global `container` in `di.py` used in many places (hard to test in isolation). Redis/cache may not be used consistently.

**Recommended next:** Prefer injecting container (or specific getters) into routers instead of global `container` where feasible. Document which middleware is required in which order. Add a simple health check that verifies DB + optional Redis.

---

## apps/auth

**Strengths:** Layered: domain (tenant, session, 2FA), application (login, refresh, logout, two_factor, demo_signup), ports (repositories), infrastructure (repos, ORM), presentation (auth_router, user_router). Login flow with 2FA and rate limiting; tenant-aware.

**Risks:** Many repositories and services; integration tests depend on overrides. Password reset / email flow may have edge cases. Session and pending_2fa tables and repos need to stay in sync with migrations.

**Recommended next:** Ensure all auth-related scripts (e.g. create_2fa_tables, reset_passwords) are documented and idempotent. Add a single “auth contract” doc (what login/refresh/logout/2FA return and when they raise).

---

## apps/users

**Strengths:** User CRUD, invite tokens, user repository; clear domain (User), application (UserService), presentation (user_router). Superuser flag and listing behavior.

**Risks:** Overlap with auth (e.g. who can list users). Invite token lifecycle and cleanup not always obvious.

**Recommended next:** Clarify boundary: auth = identity/session; users = user entity and admin CRUD. Document invite token TTL and cleanup.

---

## apps/settings

**Strengths:** User-level settings (locale, theme, etc.), settings repository, settings service and router. Fits the “user preference” use case.

**Risks:** Settings model and defaults must stay in sync with frontend and any other consumers.

**Recommended next:** Single source for default values (e.g. default locale/theme) and document in API or OpenAPI.

---

## apps/audit

**Strengths:** Audit service and repository for logging security-relevant events. Used by auth and possibly others.

**Risks:** Audit schema and retention not always visible; may grow unbounded.

**Recommended next:** Document what is audited and retention expectations; consider sampling or archiving for high-volume events.

---

## apps/chat

**Strengths:** Chat service and router; uses AI/embedding and knowledge base. Adapter layer for request/response. Clear flow: question → (optional KB) → model → answer.

**Risks:** Empty-question and edge cases (e.g. very long input) may need explicit behavior. Chat may depend on external AI; failure handling should be clear.

**Recommended next:** Define and test empty-question behavior (e.g. 400 vs 200 with “please ask a question” message). Add timeout and error response contract.

---

## apps/ai

**Strengths:** Embedding service; abstraction over embedding model. Used by knowledge and chat.

**Risks:** Model and dimension fixed in config; changing model may break existing embeddings. No versioning of embedding model in index.

**Recommended next:** Document embedding model and dimension in one place; consider storing model name/version in Qdrant metadata for future migrations.

---

## apps/knowledge

**Strengths:** Domain (kb, pii_review), application (knowledge_service, file_ingest, pii_filter), ports, infrastructure (repos), presentation (knowledge_router). File ingest with ok/empty/scanned_review_required. PII review flow: detect → review_required → confirm (store sanitized) or reject (no store). Layered and testable.

**Risks:** File ingest: OCR not implemented; scanned PDFs get `scanned_review_required` but no actual OCR. Metadata (author, etc.) not sanitized through PII; could leak PII. Chunking and embedding pipeline depend on config and Qdrant.

**Recommended next:** Make OCR “not implemented” explicit in file_ingest and API (e.g. docstring and response field). Run file metadata through PII review or at least document that metadata is not sanitized. Keep ingest status contract (ok/empty/scanned_review_required) and document it in OpenAPI or docs.

---

## apps/knowledge/pii

**Strengths:** Thin adapter only: delegates to pii_gdpr; exposes legacy API (filter_pii, apply_pii_replacements, PiiConfirmationRequiredError). entities and policy now derive from entity_registry. Sanitization: placeholders and generalization; dedupe and replace from end.

**Risks:** pii.entities and pii.sanitization must stay aligned with pii_gdpr (registry + legacy_mapping). Deprecated nlp_setup/recognizers still in tree; can be removed later.

**Recommended next:** Rely on entity_registry as single source; run a CI check that pii.entities sensitivity sets match registry. Remove nlp_setup/recognizers when no longer needed.

---

## apps/knowledge/pii_gdpr

**Strengths:** Single PII engine: detectors (regex, NER, email classifier, vehicle, technical, document IDs, bank, etc.), policy engine (risk class, recommended action, email role/org handling, date vs DOB), sanitizer, ingestion pipeline. Entity registry defines IMPLEMENTED/PARTIAL/NOT and sensitivity; legacy_mapping and policy use it. DATE vs DATE_OF_BIRTH separated.

**Risks:** Policy engine has many branches (email, date, org, location); default action mapping should be documented. Some detectors are PARTIALLY_IMPLEMENTED (format/language limited); tests should reflect that (xfail where appropriate).

**Recommended next:** Document policy decision flow (direct PII, indirect, sensitive hints, role-based email, org email, date vs DOB, location/org) and default actions (MASK, KEEP, REVIEW_REQUIRED, etc.) in one place. Strengthen tests: assert exact entity types where possible; use xfail for partial/unimplemented.

---

## scripts

**Strengths:** Utility scripts (DB schema, 2FA tables, reset passwords, etc.); some use `sys.path` to run from repo root.

**Risks:** Scripts may drift from app (e.g. table names, env vars). No single “scripts contract” doc.

**Recommended next:** List scripts in README or docs with purpose and how to run (e.g. from repo root, which env vars). Prefer `python -m scripts.xyz` or documented `python scripts/xyz.py` from repo root.

---

## tests

**Strengths:** Unit vs integration split; conftest with lazy app and fixtures (client, client_authenticated, mock services). PII and pii_gdpr unit tests; integration tests for auth, chat, knowledge, user CRUD, settings, PII pipeline.

**Risks:** Weak assertions: e.g. `assert isinstance(data, list)`, `assert r.status_code in (200, 422)`, or “any entity found” instead of “this entity type”. No pytest markers for smoke/release_acceptance; xfail used but not consistently. Empty-question chat and Spanish plate / role-based email tests may be underspecified.

**Recommended next:** Strengthen assertions: exact status code where determinism is possible; assert expected entity types in PII tests; use xfail for NOT_IMPLEMENTED or PARTIAL. Add markers: `@pytest.mark.unit`, `@pytest.mark.integration`, `@pytest.mark.smoke_only`, `@pytest.mark.release_acceptance` and document in pytest.ini. Separate “must pass before release” from “nice to have” or flaky.

---

## Summary table

| Module        | Main strength              | Main risk                    | Next refactor focus                    |
|---------------|----------------------------|-----------------------------|----------------------------------------|
| config        | Centralized settings       | Env validation              | Document + optional startup validation  |
| main          | Clear entry, middleware    | No app factory              | create_app(); dedupe imports            |
| apps/core     | DI, middleware, security   | God container, global refs  | Inject container; health check          |
| apps/auth     | Layered auth + 2FA         | Many deps, scripts          | Auth contract doc; script docs          |
| apps/users    | User CRUD, invites         | Boundary with auth          | Clarify auth vs users; invite TTL       |
| apps/settings | User preferences           | Sync with frontend          | Defaults + API doc                      |
| apps/audit    | Audit events               | Retention/growth            | Document retention                      |
| apps/chat     | Chat flow, KB integration  | Empty/question edge cases   | Empty-question contract; timeouts       |
| apps/ai       | Embedding abstraction      | Model/dimension change      | Document model; optional version in index|
| apps/knowledge| Ingest, PII, KB            | OCR missing, metadata PII   | OCR explicit; metadata handling         |
| apps/knowledge/pii   | Legacy adapter only       | Sync with registry          | Rely on registry; remove deprecated      |
| apps/knowledge/pii_gdpr | Single engine, registry | Policy complexity           | Policy doc; stronger tests              |
| scripts       | DB/2FA utilities           | Drift from app              | Script list + run instructions          |
| tests         | Unit/integration split     | Weak assertions, no markers| Stronger asserts; markers; xfail       |
