# Tesztparancsok és lint
# Használat: make lint | make test-unit | make test-integration | make test-slow

.PHONY: lint test-unit test-integration test-slow test-all install security-predeploy security-predeploy-dev rotate-jwt pii-harden pii-purge

install:
	pip install -r requirements.txt
	pip install -e .

lint:
	ruff check . --output-format=concise || true

test-unit:
	pytest tests/unit -v

test-integration:
	pytest tests/integration -v

test-slow:
	pytest -m slow -v

test-all:
	pytest tests/ -v

security-predeploy:
	python3 scripts/predeploy_security_check.py --env-file .env --proxy-config deploy/nginx/aiplaza.conf

security-predeploy-dev:
	python3 scripts/predeploy_security_check.py --env-file .env --proxy-config deploy/nginx/aiplaza.conf.example --allow-non-prod

rotate-jwt:
	python3 scripts/rotate_secrets.py --env-file .env --rotate-jwt

pii-harden:
	python3 scripts/harden_kb_personal_data.py

pii-purge:
	python3 scripts/purge_expired_pii.py
