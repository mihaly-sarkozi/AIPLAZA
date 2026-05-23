# Backend Testability Matrix

This matrix documents the minimum green test areas required for the 10/10 testability block.

| Area | Primary tests |
| --- | --- |
| URL ingest security | `backend/tests/unit/knowledge/test_url_ingest_security.py`, `backend/tests/unit/knowledge/test_url_fetch_service.py`, `backend/tests/unit/knowledge/test_url_ingest_error_codes_api.py` |
| Upload security | `backend/tests/unit/test_knowledge_api_upload_limits.py`, `backend/tests/security/test_security_regression_matrix.py` |
| Signed request verification | `backend/tests/unit/test_channel_access_origin_policy.py`, `backend/tests/unit/test_signed_request_audit_logging.py`, `backend/tests/security/test_security_regression_matrix.py` |
| JWT/session | `backend/tests/unit/test_token_service.py`, `backend/tests/unit/test_login_authenticator_policy.py`, `backend/tests/integration/test_auth_login.py`, `backend/tests/security/test_security_regression_matrix.py` |
| CSRF | `backend/tests/unit/test_csrf_middleware_platform_admin.py`, `backend/tests/security/test_security_regression_matrix.py` |
| Tenant isolation | `backend/tests/unit/knowledge/test_tenant_isolation_api_contracts.py`, `backend/tests/unit/knowledge/test_retrieval_tenant_boundary.py`, `backend/tests/unit/test_channel_access_origin_policy.py` |
| Permission policies | `backend/tests/unit/knowledge/test_corpus_permission_service.py`, `backend/tests/unit/test_chat_permission_service.py`, `backend/tests/unit/test_auth_authorization_policy.py` |
| Knowledge ingest state transitions | `backend/tests/unit/knowledge/test_ingest_run_service.py`, `backend/tests/unit/knowledge/test_ingest_progress_contract.py`, `backend/tests/unit/test_app_knowledge_facade.py` |
| Outbox retry/dead-letter | `backend/tests/unit/test_event_outbox_scaling.py`, `backend/tests/unit/test_knowledge_ingest_outbox.py`, `backend/tests/unit/test_lifecycle_router_outbox.py` |
| Chat permission | `backend/tests/unit/test_chat_permission_service.py`, `backend/tests/unit/test_channel_access_origin_policy.py`, `backend/tests/security/test_security_regression_matrix.py` |
| Prompt injection safety | `backend/tests/unit/chat/test_prompt_builder.py`, `backend/tests/security/test_security_regression_matrix.py` |
| Error response mapping | `backend/tests/unit/test_error_response_schema.py`, `backend/tests/security/test_security_regression_matrix.py` |
| Architecture boundaries | `backend/tests/architecture` |

Required test groups are present:

- `backend/tests/unit`
- `backend/tests/integration`
- `backend/tests/security`
- `backend/tests/architecture`
