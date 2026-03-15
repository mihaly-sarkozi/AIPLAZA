# tests/app_factory.py
"""
Lightweight test app factory. This is the preferred way to obtain the FastAPI app in tests.

- Use the `app` fixture from conftest for tests that need the API (it calls create_test_app).
- Do NOT import `main` or `main.app` directly in tests; that loads the full runtime too early.
- Import is deferred: main.app is loaded only when create_test_app() is first called.
"""
from __future__ import annotations


def create_test_app():
    """Return a FastAPI app suitable for tests. Loads main.app on first call (deferred import)."""
    from main import app  # noqa: PLC0415
    return app


def get_app():
    """Alias for create_test_app(). Use when a test needs the app for dependency overrides."""
    return create_test_app()
