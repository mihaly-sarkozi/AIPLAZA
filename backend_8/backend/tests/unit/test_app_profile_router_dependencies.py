from __future__ import annotations

import pytest
from fastapi.routing import APIRoute

from apps.profile.api.router import router

pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


def _get_route(path: str, method: str) -> APIRoute:
    for route in router.routes:
        if isinstance(route, APIRoute) and route.path == path and method in route.methods:
            return route
    raise AssertionError(f"Route not found: {method} {path}")


def test_update_profile_uses_body_not_query_param() -> None:
    route = _get_route("/profile", "PATCH")

    query_param_names = {param.name for param in route.dependant.query_params}
    body_param_names = {param.name for param in route.dependant.body_params}

    assert "body" not in query_param_names
    assert "body" in body_param_names
