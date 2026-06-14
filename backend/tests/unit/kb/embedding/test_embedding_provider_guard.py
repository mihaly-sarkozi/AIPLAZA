from __future__ import annotations

import pytest

from apps.kb.kb_embedding.bootstrap.embedding_provider_guard import validate_embedding_provider_runtime


def test_dummy_provider_blocked_without_allow_flag():
    settings = type(
        "S",
        (),
        {"embedding_provider": "dummy", "embedding_allow_dummy": False},
    )()
    with pytest.raises(ValueError, match="embedding_allow_dummy"):
        validate_embedding_provider_runtime(settings)


def test_dummy_provider_allowed_in_test_env():
    settings = type(
        "S",
        (),
        {"embedding_provider": "dummy", "embedding_allow_dummy": True},
    )()
    validate_embedding_provider_runtime(settings)


def test_dummy_provider_blocked_in_production(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    settings = type(
        "S",
        (),
        {"embedding_provider": "dummy", "embedding_allow_dummy": True},
    )()
    with pytest.raises(ValueError, match="production"):
        validate_embedding_provider_runtime(settings)
