from __future__ import annotations

import pytest
from fastapi.routing import APIRoute

from core.modules.users.router.admin_users_router import router

pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


def _get_route(path: str, method: str) -> APIRoute:
    for route in router.routes:
        if isinstance(route, APIRoute) and route.path == path and method in route.methods:
            return route
    raise AssertionError(f"Route not found: {method} {path}")


def test_list_users_uses_tenant_dependency_not_query_param() -> None:
    route = _get_route("/users", "GET")

    query_param_names = {param.name for param in route.dependant.query_params}
    dependency_names = {dependency.name for dependency in route.dependant.dependencies}

    assert "tenant" not in query_param_names
    assert "tenant" in dependency_names


def test_create_user_uses_body_and_tenant_dependency() -> None:
    route = _get_route("/users", "POST")

    query_param_names = {param.name for param in route.dependant.query_params}
    body_param_names = {param.name for param in route.dependant.body_params}
    dependency_names = {dependency.name for dependency in route.dependant.dependencies}

    assert "tenant" not in query_param_names
    assert "data" not in query_param_names
    assert "tenant" in dependency_names
    assert "data" in body_param_names


def test_update_user_uses_body_and_tenant_dependency() -> None:
    route = _get_route("/users/{user_id}", "PUT")

    query_param_names = {param.name for param in route.dependant.query_params}
    body_param_names = {param.name for param in route.dependant.body_params}
    dependency_names = {dependency.name for dependency in route.dependant.dependencies}

    assert "tenant" not in query_param_names
    assert "data" not in query_param_names
    assert "tenant" in dependency_names
    assert "data" in body_param_names
