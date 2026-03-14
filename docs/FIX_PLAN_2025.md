# Fix plan: bootstrap, tests, PII, cleanup

## A. Diagnosis (remaining problems)

1. **Test bootstrap / import**
   - `tests/conftest.py` imports at top level: `config.settings`, `apps.core.di`, `apps.core.security.auth_dependencies`, `apps.core.container.app_container`, `apps.auth.application.dto`, `apps.users.domain.user`, `apps.auth.domain.tenant`. Pytest collection therefore loads the full config and app dependencies; if `config` is missing or broken, collection fails immediately.
   - No lightweight test app: tests always use the production app from `main.py` via `get_app()`.

2. **Legacy PII layer**
   - `apps.knowledge.pii` is already thin (pipeline → adapter → pii_gdpr; pii_filter → adapter). No duplicate detection logic. Only cleanup: ensure no dead code and docstrings state single source of truth.

3. **Weak tests**
   - Chat: empty-question test accepts both 200 and 422; API allows empty string because `AskRequest.question` has no `min_length`.
   - `test_user_crud`, `test_knowledge`: only `assert isinstance(data, list)`.
   - `test_pii_pipeline` (TestNemImplementaltTipusok): several tests only `assert isinstance(matches, list)` and do not assert exact entity type where determinism is possible.

4. **PII/GDPR tests**
   - Spanish plate and role-based email tests already assert exact entity/outcome. Add `@pytest.mark.release_acceptance` where appropriate; ensure file ingest and review flow tests have strict assertions.

5. **Test categories**
   - Markers exist in pytest.ini (unit, integration, release_acceptance, smoke_only, xfail). Not all tests are consistently marked; xfail is used in PII not-implemented tests.

6. **File ingest**
   - OCR not implemented; statuses ok/empty/scanned_review_required are correct and documented. No change needed beyond keeping docstrings explicit.

7. **Archive / project noise**
   - `.gitignore` already has `.DS_Store`. Add `__MACOSX/`, `node_modules/`, and common frontend build dirs so the repo stays clean.

---

## B. File-by-file fix plan

| File | Problem | Change | Why |
|------|--------|--------|-----|
| `tests/conftest.py` | Top-level imports of config and apps pull full stack at collection. | Move all `config.*` and `apps.*` imports inside `get_app()` and inside fixtures that need them. Top-level keep only: `os`, `pytest`, `datetime`, `timezone`, `MagicMock`, `patch`, `TestClient`. | Collection can run without config/apps; fixtures import only when used. |
| `tests/app_factory.py` (new) | No lightweight app for tests. | Add `create_test_app()` that returns the same app as `get_app()` (for now); document that it can later be replaced with a minimal app (routers only, no DB lifespan). | Single place for test app creation; future minimal app without changing main. |
| `apps/chat/adapter/http/request.py` | `question: str` allows empty string. | Add `Field(..., min_length=1)` so empty question is invalid. | API returns 422 for empty question; one correct behavior. |
| `tests/integration/test_chat.py` | Empty-question test accepts 200 or 422. | Assert `r.status_code == 422` and validate error detail. | Test proves the chosen behavior. |
| `tests/integration/test_user_crud.py` | Only `assert isinstance(data, list)`. | Keep isinstance; add assert on response structure (e.g. keys or length when relevant). | Stronger gate without over-specifying. |
| `tests/integration/test_knowledge.py` | Only `assert isinstance(data, list)`. | Same: assert structure (e.g. list of dicts with expected keys). | Same. |
| `tests/integration/test_pii_pipeline.py` | xfail tests only assert `isinstance(matches, list)`. | In xfail tests keep list check but add comment that when implemented, assert exact entity type. One test that expects specific entity: assert exact type. | Clear intent; when xfail removed, assertion is already there. |
| `.gitignore` | Archive junk can appear. | Add `__MACOSX/`, `node_modules/`, `frontend/dist/`, `frontend/build/`. | Cleaner repo and archives. |

---

## E. Run instructions

- **Install dependencies:** From repo root: `pip install -e .` or `pip install -r requirements.txt` (if present). Ensure `.env` exists or required env vars are set (e.g. `DATABASE_URL`, `tenant_base_domain`) for integration tests.
- **Run all tests:** From repo root: `pytest`
- **Unit only (no app stack):** `pytest tests/unit/ -v`
- **Integration only:** `pytest tests/integration/ -v`
- **Release acceptance (quality gate):** `pytest -m release_acceptance -v`
- **Smoke only:** `pytest -m smoke_only -v`
- **Without slow:** `pytest -m "not slow" -v`

## F. Remaining limitations

- **OCR:** Not implemented. Scanned PDFs return `scanned_review_required`; they are not OCR’d or auto-indexed.
- **Config at collection:** If `config` package is missing or broken, only tests that request `app` or fixtures needing config will fail; collection itself no longer imports config.
- **Lightweight app:** `create_test_app()` currently returns the same app as production; a future minimal app (routers only, no DB/Redis lifespan) is not implemented.
- **PII:** Some entity types are PARTIALLY_IMPLEMENTED or NOT_IMPLEMENTED (see entity_registry); xfail tests document not-yet-implemented behavior (e.g. GPS, becenév).
- **File metadata:** Extracted metadata (author, etc.) is not run through PII sanitization; document in API if needed.
