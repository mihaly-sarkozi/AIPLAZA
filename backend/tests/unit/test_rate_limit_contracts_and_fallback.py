from __future__ import annotations

import ast
from types import SimpleNamespace
from pathlib import Path

import pytest

from core.kernel.security.errors import SecurityConfigError
from core.kernel.security.rate_limit import enforce_fallback_throttle
from core.kernel.security.rate_limit_guards import validate_production_redis_url
import core.kernel.security.rate_limit as rate_limit_module

pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


def _module_has_limited_route(
    module_path: str,
    *,
    method: str,
    route: str,
    limit_value: str | None = None,
    limit_lambda_contains: str | None = None,
) -> bool:
    tree = ast.parse(Path(module_path).read_text(encoding="utf-8"))
    target = method.lower()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        decorators = list(node.decorator_list)
        route_match = False
        limit_match = False
        for decorator in decorators:
            if (
                isinstance(decorator, ast.Call)
                and isinstance(decorator.func, ast.Attribute)
                and isinstance(decorator.func.value, ast.Name)
                and decorator.func.value.id == "router"
                and decorator.func.attr == target
                and decorator.args
                and isinstance(decorator.args[0], ast.Constant)
                and decorator.args[0].value == route
            ):
                route_match = True
            if (
                isinstance(decorator, ast.Call)
                and isinstance(decorator.func, ast.Attribute)
                and isinstance(decorator.func.value, ast.Name)
                and decorator.func.value.id == "limiter"
                and decorator.func.attr == "limit"
            ):
                if (
                    limit_value is not None
                    and decorator.args
                    and isinstance(decorator.args[0], ast.Constant)
                    and decorator.args[0].value == limit_value
                ):
                    limit_match = True
                if (
                    limit_lambda_contains is not None
                    and decorator.args
                    and isinstance(decorator.args[0], ast.Lambda)
                    and limit_lambda_contains in ast.unparse(decorator.args[0])
                ):
                    limit_match = True
        if route_match and limit_match:
            return True
    return False


def test_auth_login_route_has_rate_limit_contract() -> None:
    assert _module_has_limited_route(
        "core/modules/auth/router/auth_router.py",
        method="POST",
        route="/auth/login",
        limit_lambda_contains="rate_limit_login_per_minute",
    )


def test_channel_chat_route_has_rate_limit_contract() -> None:
    assert _module_has_limited_route(
        "apps/chat/router/channel_router.py",
        method="POST",
        route="/channel/chat",
        limit_value="120/minute",
    )


def test_kb_create_route_has_rate_limit_contract() -> None:
    assert _module_has_limited_route(
        "apps/kb/kb_crud/router/KnowledgeBaseRouter.py",
        method="POST",
        route="",
        limit_value="5/minute",
    )


def test_fallback_throttle_blocks_after_memory_limit_without_redis(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rate_limit_module, "get_redis", lambda: None)
    with rate_limit_module._fallback_lock:
        rate_limit_module._fallback_buckets.clear()

    request = SimpleNamespace(
        method="GET",
        url=SimpleNamespace(path="/api/auth/csrf-token"),
        state=SimpleNamespace(tenant_slug="demo"),
        client=SimpleNamespace(host="127.0.0.1"),
    )

    for _ in range(120):
        allowed, _ = enforce_fallback_throttle(request)
        assert allowed is True

    allowed, reason = enforce_fallback_throttle(request)
    assert allowed is False
    assert "Too many requests" in reason


def test_production_guard_requires_redis_url() -> None:
    with pytest.raises(SecurityConfigError, match="redis_url staging/production"):
        validate_production_redis_url(SimpleNamespace(redis_url=""), "production")
