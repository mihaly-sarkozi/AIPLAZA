# Tesztparancsok és lint
# Használat: make lint | make test-unit | make test-integration | make test-slow
#
# test-unit: csak tests/unit – nem tölti a tests/integration/conftest app/DB fixture-ét.
# test-integration: HTTP/TestClient/PostgreSQL igényű tesztek.

.PHONY: lint format typecheck test test-unit test-integration test-slow test-all install install-dev package check-no-runtime-ddl check-import-boundaries \
	claim-regression claim-regression-hu claim-regression-en claim-regression-es \
	knowledge-dirty-check

install:
	cd backend && pip install -r requirements.txt
	cd backend && pip install -e .

install-dev:
	cd backend && pip install -r requirements-dev.txt
	cd backend && pip install -e ".[test]"

lint:
	cd backend && ruff check . --output-format=concise

format:
	cd backend && ruff format .

typecheck:
	cd backend && mypy

test:
	cd backend && pytest

test-unit:
	cd backend && pytest tests/unit -v --tb=short

test-integration:
	cd backend && pytest tests/integration -v --tb=short

test-slow:
	cd backend && pytest -m slow -v

test-all:
	cd backend && pytest tests/ -v --tb=short

package:
	./scripts/package_backend.sh

check-no-runtime-ddl:
	python3 scripts/check_no_runtime_ddl.py

check-import-boundaries:
	python3 scripts/check_import_boundaries.py

# Refaktor sorrend (13.): nyelvenként claim regresszió, majd local resolver füst.
claim-regression:
	PYTHONPATH=backend python3 scripts/dev_knowledge_claim_regression.py --lang all

claim-regression-hu:
	PYTHONPATH=backend python3 scripts/dev_knowledge_claim_regression.py --lang hu

claim-regression-en:
	PYTHONPATH=backend python3 scripts/dev_knowledge_claim_regression.py --lang en

claim-regression-es:
	PYTHONPATH=backend python3 scripts/dev_knowledge_claim_regression.py --lang es

knowledge-dirty-check: claim-regression
	PYTHONPATH=backend python3 scripts/dev_knowledge_local_resolver_smoke.py