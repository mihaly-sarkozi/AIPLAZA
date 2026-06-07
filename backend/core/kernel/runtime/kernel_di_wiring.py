# backend/core/kernel/runtime/kernel_di_wiring.py
# Feladat: Az AppContainer által felépített gyakori platform service-eket beköti a kernel dependency façade-ba. Audit, token, login, refresh, logout, permission, tenant és user repository eléréseket publikál a régi/kernel DI felület felé. Core runtime wiring modul, amely assembly után teszi elérhetővé a közös függőségeket.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from core.kernel.deps.facade import configure_kernel_dependencies, register_service
from core.kernel.bootstrap.infrastructure_registry import InfrastructureRegistry
from core.kernel.interface.keys import PLATFORM_JOB_QUEUE
from core.kernel.security.permission_service import PermissionService


def wire_kernel_dependencies(
    *,
    audit_service: object,
    token_service: object,
    login_service: object,
    refresh_service: object,
    logout_service: object,
    permission_service: PermissionService,
    event_channel: object,
    infrastructure: InfrastructureRegistry,
) -> None:
    """Regisztrálja a gyakori platform service-eket a kernel DI konténerben."""
    repos = infrastructure.repositories
    configure_kernel_dependencies(
        audit_service=audit_service,
        token_service=token_service,
        login_service=login_service,
        refresh_service=refresh_service,
        logout_service=logout_service,
        permission_service=permission_service,
        tenant_repository=repos.tenant_repo,
        user_repository=repos.user_repo,
    )
    register_service(PLATFORM_JOB_QUEUE, event_channel)

