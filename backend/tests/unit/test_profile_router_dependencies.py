from __future__ import annotations

import pytest
from fastapi.routing import APIRoute

from core.modules.users.router.profile_router import router

pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


def _get_route(path: str, method: str) -> APIRoute:
    for route in router.routes:
        if isinstance(route, APIRoute) and route.path == path and method in route.methods:
            return route
    raise AssertionError(f"Route not found: {method} {path}")


def test_set_initial_password_uses_body_not_query_param() -> None:
    route = _get_route("/auth/me/set-initial-password", "POST")

    query_param_names = {param.name for param in route.dependant.query_params}
    body_param_names = {param.name for param in route.dependant.body_params}

    assert "body" not in query_param_names
    assert "body" in body_param_names
