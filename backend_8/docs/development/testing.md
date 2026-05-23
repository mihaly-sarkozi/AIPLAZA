# Testing And Development Checks

## Telepites

Backend dev/test kornyezet:

```bash
cd backend
python -m pip install -r requirements-dev.txt
python -m pip install -e ".[test]"
```

Python 3.11 ajanlott CI-vel egyezoen. Python 3.14 alatt nehany nagy dependency wheel hianya miatt forrasbol buildelhet.

## Gyors parancsok

Repo gyokerbol:

```bash
make lint
make format
make typecheck
make test
make test-unit
make test-integration
make check-no-runtime-ddl
make check-import-boundaries
make package
```

Backend konyvtarbol:

```bash
pytest tests/unit -v --tb=short
pytest tests/integration -v --tb=short
ruff check .
ruff format .
mypy
python -m compileall .
```

## Teszt env

Unit tesztekhez a `backend/tests/conftest.py` allit be alap env ertekeket:

- `APP_ENV=test`
- `JWT_SECRET`
- `JWT_ISSUER`
- `JWT_AUDIENCE`
- `DATABASE_URL=sqlite+pysqlite:///:memory:`
- `REDIS_URL=` ures, hogy local/test fallback mukodjon
- object storage, SMTP es Qdrant test placeholder ertekek

Unit teszt ne igenyeljen valodi Redis/Object Storage/SMTP kapcsolatot.

## Lint es format

Konfiguracio:

- `backend/pyproject.toml`
- `ruff` lint: `E`, `F`, `I`, `B`, `UP`, `SIM`
- `ruff format`
- `mypy` fokozatosan, jelenleg szuk modul scope-pal

Az `E501` sorhossz kezdetben ignore-olva van, hogy a bevezetes ne legyen egyszerre nagy refaktor.

## Security regression tesztek

Fontosabb celzott tesztek:

- URL ingest: `backend/tests/unit/knowledge/test_url_ingest_security.py`
- URL ingest API error code: `backend/tests/unit/knowledge/test_url_ingest_error_codes_api.py`
- upload limitek: `backend/tests/unit/test_knowledge_api_upload_limits.py`
- object storage key: `backend/tests/unit/knowledge/test_source_storage_service.py`
- outbox/internal endpoint: `backend/tests/unit/test_lifecycle_router_outbox.py`
- signed request audit: `backend/tests/unit/test_signed_request_audit_logging.py`
- tenant izolacio: `backend/tests/unit/knowledge/test_tenant_isolation_api_contracts.py`

## Architecture checks

Runtime DDL tiltasa:

```bash
make check-no-runtime-ddl
```

Import boundary:

```bash
make check-import-boundaries
```

Ezek CI-ben is futnak.

## Csomagolas ellenorzese

```bash
make package
```

Vagy kozvetlenul:

```bash
bash scripts/package_backend.sh /tmp/backend_clean.zip
```

A zip ne tartalmazzon:

- `__MACOSX`
- `.DS_Store`
- `._*`
- `__pycache__`
- `.pyc`
- `.venv`
- `node_modules`
