from __future__ import annotations

import pytest
from admin.router.admin_router import router as platform_admin_router
from apps.chat.router.channel_credentials_router import router as channel_credentials_router
from apps.chat.router.chat_router import router as chat_router
from apps.kb.kb_crud.router import router as kb_crud_router
from core.kernel.domain.router import router as domain_router
from core.kernel.http.responses import (
    ErrorResponse,
    OperationStatus,
    OperationStatusResponse,
    PageResponse,
)
from core.modules.auth.router.auth_router import router as auth_router
from core.modules.users.router.admin_users_router import router as admin_users_router
from core.modules.users.router.invite_router import router as invite_router
from core.modules.users.router.profile_router import router as profile_router

pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


def _response_model_for(router, path: str, method: str):
    wanted_method = method.upper()
    for route in router.routes:
        methods = set(getattr(route, "methods", set()) or set())
        if getattr(route, "path", "") == path and wanted_method in methods:
            return getattr(route, "response_model", None)
    raise AssertionError(f"Route not found: {method} {path}")


def test_common_operation_status_response_schema_is_stable() -> None:
    payload = OperationStatusResponse(message="done", details={"id": 1}).model_dump(mode="json", exclude_none=True)

    assert payload == {"status": "ok", "message": "done", "details": {"id": 1}}
    assert OperationStatus.SKIPPED.value == "skipped"


def test_common_error_and_page_response_schemas_are_stable() -> None:
    error = ErrorResponse(code="VALIDATION_ERROR", message="Invalid request.").model_dump(mode="json", exclude_none=True)
    page = PageResponse[int](items=[1, 2], total=2, limit=10, offset=0).model_dump(mode="json", exclude_none=True)

    assert error == {"code": "VALIDATION_ERROR", "message": "Invalid request."}
    assert page == {"items": [1, 2], "total": 2, "limit": 10, "offset": 0}


def test_mutating_success_routes_use_operation_status_response_model() -> None:
    route_expectations = [
        (auth_router, "POST", "/auth/logout"),
        (profile_router, "POST", "/auth/forgot-password"),
        (profile_router, "POST", "/auth/me/change-password"),
        (profile_router, "POST", "/auth/me/demo-unsubscribe"),
        (invite_router, "POST", "/users/set-password"),
        (admin_users_router, "DELETE", "/users/{user_id}"),
        (domain_router, "POST", "/platform/domain/custom/delete"),
        (chat_router, "POST", "/chat/feedback"),
        (channel_credentials_router, "POST", "/channel/credentials/{credential_id}/revoke"),
        (kb_crud_router, "PUT", "/kb/{kb_id}/permissions"),
        (kb_crud_router, "DELETE", "/kb/{kb_id}"),
        (platform_admin_router, "POST", "/platform-admin/auth/logout"),
        (platform_admin_router, "POST", "/platform-admin/auth/mfa/disable"),
        (platform_admin_router, "POST", "/platform-admin/auth/me/change-password"),
        (platform_admin_router, "DELETE", "/platform-admin/monitoring/security/ban-ip/{ip}"),
    ]

    for router, method, path in route_expectations:
        assert _response_model_for(router, path, method) is OperationStatusResponse


def test_platform_admin_simulated_date_routes_use_debug_date_response_model() -> None:
    from admin.web.schemas.platform_admin_schemas import PlatformAdminDebugDateResponse

    assert _response_model_for(platform_admin_router, "/platform-admin/debug/simulated-date", "GET") is PlatformAdminDebugDateResponse
    assert _response_model_for(platform_admin_router, "/platform-admin/debug/simulated-date", "PUT") is PlatformAdminDebugDateResponse
    assert _response_model_for(platform_admin_router, "/platform-admin/debug/simulated-date", "DELETE") is PlatformAdminDebugDateResponse
