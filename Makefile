# Tesztparancsok és lint
# Használat: make lint | make test-unit | make test-integration | make test-slow

.PHONY: lint test-unit test-integration test-slow test-all install

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
