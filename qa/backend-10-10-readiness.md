# Backend 10/10 Readiness Gate

Last measured: 2026-05-23

## Current Gate Result

The backend is not yet 10/10 complete because two mega-service gates are still open:

- `backend/apps/knowledge/service/knowledge_facade.py`: 6583 lines
- `backend/apps/chat/service/chat_service.py`: 2686 lines

`backend/apps/chat/router/chat_router.py` is currently 281 lines, so the chat router size gate is within the target range.

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
- API operation responses use shared DTOs from `core.kernel.http.responses`.
- Audit access for apps goes through `core.kernel.audit`.
- Permission decisions have central services for knowledge and chat.

## Remaining 10/10 Blockers

1. Decompose `KnowledgeFacade` until it is a compatibility/orchestration layer below the agreed target.
2. Decompose `ChatService` until chat flow is a thin pipeline below the agreed target.
3. Continue moving large validation and policy clusters out of mega services into focused components when touched.

## Definition Of Done

The backend can be called 10/10 complete when all green gates remain green and both mega-service blockers above are closed with focused regression tests.
