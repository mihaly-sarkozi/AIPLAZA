from __future__ import annotations

from unittest.mock import patch

import pytest

from core.kernel.config.bootstrap_guards import (
    ConfigBootstrapError,
    validate_config_bootstrap_contract,
)

pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


def test_test_env_allows_env_var_only_bootstrap_without_env_file(monkeypatch: pytest.MonkeyPatch) -> None:
    from core.kernel.config import config_loader

    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setattr(
        config_loader,
        "get_env_file_status",
        lambda: {"env_exists": False, "env_path": "/missing/.env"},
    )

    validate_config_bootstrap_contract("test")


def test_local_env_requires_env_file(monkeypatch: pytest.MonkeyPatch) -> None:
    from core.kernel.config import config_loader

    monkeypatch.setenv("APP_ENV", "local")
    monkeypatch.setattr(
        config_loader,
        "get_env_file_status",
        lambda: {"env_exists": False, "env_path": "/missing/.env"},
    )

    validate_config_bootstrap_contract("local")


def test_production_requires_explicit_env_vars_not_env_file_values(monkeypatch: pytest.MonkeyPatch) -> None:
    from core.kernel.config import config_loader

    required = (
        "APP_ENV",
        "DATABASE_URL",
        "JWT_SECRET",
        "JWT_ISSUER",
        "JWT_AUDIENCE",
        "FRONTEND_BASE_URL",
        "CORS_ORIGINS",
        "TRUSTED_HOSTS",
        "TENANT_BASE_DOMAIN",
        "REDIS_URL",
        "SMTP_HOST",
        "SMTP_USER",
        "SMTP_PASSWORD",
        "SMTP_FROM_EMAIL",
    )
    env = {name: "configured" for name in required}
    env["APP_ENV"] = "production"

    with patch.dict("os.environ", env, clear=True):
        monkeypatch.setattr(
            config_loader,
            "get_env_file_status",
            lambda: {"env_exists": True, "env_path": "/repo/backend/.env"},
        )
        monkeypatch.setattr(config_loader, "is_env_var_explicitly_set", lambda name: name != "DATABASE_URL")

        with pytest.raises(ConfigBootstrapError, match="DATABASE_URL"):
            validate_config_bootstrap_contract("production")
