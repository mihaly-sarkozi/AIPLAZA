# backend/core/modules/tenant/middleware/tenant_middleware.py
# Feladat: A tenant feloldást végző ASGI middleware implementációja. Host alapján tenant snapshotot keres, request state-be és ContextVarba írja a tenant contextet, lifecycle státusz alapján blokkolhat, és observability adatokat állít be. Request hot path tenant integráció.
# Sárközi Mihály - 2026.05.21

import asyncio
import time
from starlette.types import ASGIApp, Receive, Scope, Send

from core.modules.tenant.dto import TenantDomainInfo
from core.modules.tenant.repositories import TenantRepository
from core.modules.tenant.context.tenant_context import current_tenant_schema
from core.modules.tenant.routing.request_state import apply_tenant_snapshot, initialize_tenant_state
from core.modules.tenant.routing.resolution import TenantResolutionService
from core.kernel.http.error_payloads import build_error_body_bytes_for_scope
from core.kernel.logging.observability import bind_observability_context, increment_metric, reset_observability_context
from core.kernel.logging.request_timing import log_timing_debug, log_timing_warning, record_span
from core.modules.tenant.domain.tenant_policy import DomainRoutingPolicy, TenantLifecyclePolicy

_TENANT_OPTIONAL_PATH_PREFIXES = (
    "/api/health",
    "/api/health/live",
    "/api/health/ready",
    "/api/auth/csrf-token",
    "/api/metrics",
    "/api/platform-admin/",
    "/api/platform/lifecycle",
    "/api/installer/",
)


# Ez a függvény visszaadja a(z) header logikáját.
def _get_header(scope: Scope, name: str) -> str | None:
    name_lower = name.encode().lower()
    for k, v in scope.get("headers", []):
        if k.lower() == name_lower:
            return v.decode("latin-1")
    return None


# Ez az aszinkron függvény a(z) send_json_response logikáját valósítja meg.
async def _send_json_response(scope: Scope, send: Send, status: int, body: dict) -> None:
    body_bytes = build_error_body_bytes_for_scope(
        scope=scope,
        status_code=status,
        detail=body.get("detail"),
    )
    await send({
        "type": "http.response.start",
        "status": status,
        "headers": [[b"content-type", b"application/json"]],
    })
    await send({"type": "http.response.body", "body": body_bytes})

class TenantMiddleware:
    """ASGI: Host → slug → egységes tenant snapshot cache."""

    # Ez a metódus a Python-specifikus speciális működést valósítja meg.
    def __init__(
        self,
        app: ASGIApp,
        tenant_repo: TenantRepository,
        base_domain: str,
        multi_tenant_enabled: bool = True,
        install_host: str | None = None,
        single_tenant_slug: str | None = "demo",
        localhost_tenant: str | None = "demo",
        routing_policy: DomainRoutingPolicy | None = None,
        lifecycle_policy: TenantLifecyclePolicy | None = None,
    ) -> None:
        self.app = app
        self._base_domain = base_domain.strip().lower()
        self._multi_tenant_enabled = multi_tenant_enabled
        self._install_host = (install_host or "").strip().lower() or None
        self._single_tenant_slug = (single_tenant_slug or "").strip() or None
        self._localhost_tenant = localhost_tenant
        self._routing_policy = routing_policy or DomainRoutingPolicy(
            tenant_base_domain=self._base_domain,
            localhost_tenant=localhost_tenant,
        )
        self._lifecycle_policy = lifecycle_policy or TenantLifecyclePolicy()
        self._resolution_service = TenantResolutionService(
            tenant_repo=tenant_repo,
            routing_policy=self._routing_policy,
        )

    # Ez az aszinkron metódus a Python-specifikus speciális működést valósítja meg.
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path = scope.get("path", "")
        is_installer_path = path.startswith("/api/installer/")
        is_csrf_token_path = path.startswith("/api/auth/csrf-token")
        is_platform_admin_path = path.startswith("/api/platform-admin/")
        is_tenant_optional_path = any(path.startswith(prefix) for prefix in _TENANT_OPTIONAL_PATH_PREFIXES)
        state = initialize_tenant_state(scope)
        state["tenant_resolution_outcome"] = "not_evaluated"
        token = current_tenant_schema.set(None)
        observability_token = None

        host = (_get_header(scope, "host") or "").split(":")[0].strip().lower()
        if not host:
            if path.startswith("/api") and not is_tenant_optional_path:
                state["tenant_resolution_outcome"] = "missing_host"
                increment_metric("platform.tenant.resolution.failure.count", 1.0, tags={"reason": "missing_host"})
                log_timing_debug("tenant.middleware.reject_no_host", path=scope.get("path", ""))
                await _send_json_response(
                    scope, send, 400,
                    {"detail": "Tenant hiányzik. Használd a céges aldomaint (pl. http://demo.local:8001)."}
                )
                current_tenant_schema.reset(token)
                return
            try:
                await self.app(scope, receive, send)
            finally:
                current_tenant_schema.reset(token)
            return

        t0 = time.monotonic()
        loop = asyncio.get_event_loop()
        if self._multi_tenant_enabled:
            allowed_install_hosts = {
                value.strip().lower()
                for value in (self._install_host, self._base_domain)
                if value and value.strip()
            }
            if is_tenant_optional_path:
                if is_platform_admin_path:
                    slug = None
                    is_custom_domain = False
                    snapshot = None
                elif is_csrf_token_path and host not in allowed_install_hosts:
                    csrf_slug, _is_custom, _snapshot = await loop.run_in_executor(
                        None,
                        lambda: self._resolution_service.resolve_request(host),
                    )
                    if not csrf_slug:
                        state["tenant_resolution_outcome"] = "install_host_rejected"
                        increment_metric("platform.tenant.resolution.failure.count", 1.0, tags={"reason": "install_host_rejected"})
                        await _send_json_response(
                            scope, send, 400,
                            {"detail": "Tenant hiányzik, vagy a host install útvonal nincs engedélyezve."}
                        )
                        current_tenant_schema.reset(token)
                        return
                    slug = None
                    is_custom_domain = False
                    snapshot = None
                else:
                    if allowed_install_hosts and host not in allowed_install_hosts:
                        state["tenant_resolution_outcome"] = "install_host_rejected"
                        increment_metric("platform.tenant.resolution.failure.count", 1.0, tags={"reason": "install_host_rejected"})
                        await _send_json_response(
                            scope, send, 400,
                            {"detail": "Tenant hiányzik, vagy a host install útvonal nincs engedélyezve."}
                        )
                        current_tenant_schema.reset(token)
                        return
                    slug = None
                    is_custom_domain = False
                    snapshot = None
            else:
                slug, is_custom_domain, snapshot = await loop.run_in_executor(
                    None,
                    lambda: self._resolution_service.resolve_request(host),
                )
        else:
            install_host = self._install_host or host
            if host != install_host:
                await _send_json_response(
                    scope, send, 404,
                    {"detail": f"A rendszer csak ezen a hoston érhető el: {install_host}"}
                )
                current_tenant_schema.reset(token)
                return
            if is_installer_path:
                slug = None
            else:
                slug = self._single_tenant_slug
            is_custom_domain = False
            snapshot = self._resolution_service.get_snapshot(slug) if slug else None

        if slug:
            elapsed_ms = (time.monotonic() - t0) * 1000
            record_span("tenant_resolve", elapsed_ms)
            log_timing_debug(
                "tenant.middleware.lookup",
                slug=slug,
                host=host,
                elapsed_ms=round(elapsed_ms, 2),
                is_custom_domain=is_custom_domain,
            )
            if elapsed_ms > 1000:
                log_timing_warning(
                    "tenant.lookup.slow",
                    slug=slug,
                    host=host,
                    elapsed_ms=round(elapsed_ms, 2),
                    is_custom_domain=is_custom_domain,
                )
            if not snapshot or snapshot.tenant_id is None:
                state["tenant_resolution_outcome"] = "unknown_tenant"
                increment_metric("platform.tenant.resolution.failure.count", 1.0, tags={"reason": "unknown_tenant"})
                log_timing_debug(
                    "tenant.middleware.unknown_tenant",
                    slug=slug,
                    host=host,
                    elapsed_ms=round((time.monotonic() - t0) * 1000, 2),
                )
                await _send_json_response(
                    scope, send, 404,
                    {"detail": "404"}
                )
                current_tenant_schema.reset(token)
                return
            domain_info = TenantDomainInfo(
                request_host=host,
                resolved_host=host,
                is_custom_domain=is_custom_domain,
                verified_at=(snapshot.domain.verified_at if snapshot.domain else None),
            )
            snapshot = snapshot.with_domain(domain_info)
            try:
                self._lifecycle_policy.assert_routable(snapshot)
            except ValueError:
                state["tenant_resolution_outcome"] = "inactive_tenant"
                increment_metric("platform.tenant.resolution.failure.count", 1.0, tags={"reason": "inactive_tenant"})
                log_timing_debug(
                    "tenant.middleware.inactive_tenant",
                    slug=snapshot.slug,
                    host=host,
                )
                await _send_json_response(
                    scope, send, 404,
                    {"detail": "404"}
                )
                current_tenant_schema.reset(token)
                return
            apply_tenant_snapshot(state, snapshot)
            state["tenant_resolution_outcome"] = "resolved"
            current_tenant_schema.set(snapshot.slug)
            observability_token = bind_observability_context(
                tenant_id=snapshot.tenant_id,
                tenant_slug=snapshot.slug,
            )
        elif path.startswith("/api") and not is_tenant_optional_path:
            # Health és installer útvonalak tenant nélkül is elérhetők.
            state["tenant_resolution_outcome"] = "missing_tenant"
            increment_metric("platform.tenant.resolution.failure.count", 1.0, tags={"reason": "missing_tenant"})
            log_timing_debug("tenant.middleware.missing_tenant", path=scope.get("path", ""), host=host)
            await _send_json_response(
                scope, send, 400,
                {"detail": "Tenant hiányzik. Használd a céges aldomaint (pl. http://demo.local:8001)."}
            )
            current_tenant_schema.reset(token)
            return

        try:
            await self.app(scope, receive, send)
        finally:
            if observability_token is not None:
                reset_observability_context(observability_token)
            current_tenant_schema.reset(token)
