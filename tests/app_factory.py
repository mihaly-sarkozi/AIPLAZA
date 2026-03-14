# tests/app_factory.py
"""
Lightweight test app factory. Use this in fixtures so tests can boot the API in a controlled way.
Currently returns the same app as main (get_app). Can be replaced with a minimal app
(routers only, no DB/Redis lifespan) for tests that do not need the full stack.
"""
from __future__ import annotations


def create_test_app():
    """Return a FastAPI app suitable for tests. Optionally override deps on the returned app."""
    from main import app
    return app
