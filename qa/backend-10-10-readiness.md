# Backend 10/10 Readiness Gate

Last measured: 2026-05-24

## Current Gate Result

The previous mega-service blockers are closed. The backend is in final readiness verification:

- `backend/apps/knowledge/service/knowledge_facade.py`: 76 lines
- `backend/apps/chat/service/chat_service.py`: 671 lines
- `backend/apps/knowledge/service/ingest_item_processor.py`: 428 lines
- `backend/apps/knowledge/service/knowledge_trace_service.py`: 127 lines
- `backend/apps/knowledge/service/knowledge_trace_payload_builder.py`: 395 lines
- `backend/apps/knowledge/service/knowledge_trace_subject_context.py`: 144 lines

`backend/apps/chat/router/chat_router.py` remains within the target range.

## Green Gates

- Architecture tests: `tests/architecture`
- Security regression tests: `tests/security`
- Tenant isolation tests:
  - `tests/unit/knowledge/test_tenant_isolation_api_contracts.py`
  - `tests/unit/knowledge/test_retrieval_tenant_boundary.py`
  - `tests/unit/test_channel_access_origin_policy.py`
- Worker execution mode no longer advertises unsupported process mode.
- Legacy ingest routes are removed or locked.
- Error handling uses `AppError`, `ErrorMapper`, and the unified HTTP error payload.
- Chat and knowledge modules have module-specific `AppError` subclasses in `backend/apps/chat/errors.py` and `backend/apps/knowledge/errors.py`.
- API operation responses use shared DTOs from `core.kernel.http.responses`.
- Audit access for apps goes through `core.kernel.audit`.
- Permission decisions have central services for knowledge and chat.
- `ChatService` constructor wiring is delegated to `backend/apps/chat/service/chat_service_factory.py`.
- `KnowledgeFacade` constructor wiring is delegated through `backend/apps/knowledge/service/knowledge_facade_factory.py` and facade runtime wiring modules.
- `IngestItemProcessor` delegates cleanup, source creation, reprocess, semantic index refresh, progress, duplicate, completion, validation, and failure handling to focused services.
- `KnowledgeTraceService` delegates query loading, payload helpers, subject-context helpers, and quality summary handling to focused modules.
- Rejected claim diagnostics persistence is documented as a deliberate `diagnostic_persistence_decision`, not a dangling TODO.
- Skip-reason audit command attempted locally:
  - host Python: blocked because the active Python 3.14 environment has no `pytest`
  - Docker: `tests/security` is not present in the container image
  - Docker `tests/unit tests/integration tests/architecture -rs`: reached `1085 passed`, then stopped with `88` integration setup errors before skip output; root cause is `openai.AsyncOpenAI` resolving to `object` in the container and failing with `TypeError: object() takes no arguments` during chat module wiring
- Verified locally in a Python 3.12 virtual environment:
  - `tests/security`: 6 passed
  - `tests/architecture`: 11 passed
  - `tests/unit`: 1180 passed
  - compile check for touched modules: passed
  - IDE lint diagnostics for touched modules: clean
  - targeted URL ingest/fetch/object-storage security unit tests remain covered by the unit suite
- `tests/integration` currently does not complete in the local SQLite-backed setup:
  - result: 51 passed, 1 xfailed, 26 failed, 126 errors
  - primary setup blocker: tenant schema migration executes PostgreSQL schema DDL (`CREATE SCHEMA IF NOT EXISTS public`) against SQLite during `ensure_demo_test_tenant`

## Remaining 10/10 Blockers

1. Run `pytest tests/integration` against the intended PostgreSQL-compatible integration environment, or make the integration tenant schema fixture skip PostgreSQL-only DDL when the engine dialect is SQLite.
2. Keep newly touched service modules below the agreed size envelope; if a helper grows beyond the target, split it by domain responsibility.
3. Treat future trace diagnostic persistence as a schema-versioned migration, not an ad hoc metadata expansion.
4. Review the full `-rs` skip output after each test-suite expansion and ensure no security/integration skip is caused by missing implementation.

## Definition Of Done

The backend can be called 10/10 complete when all green gates remain green, the full backend test suite is proven locally, and no critical service has a dangling TODO or oversized orchestration method.
