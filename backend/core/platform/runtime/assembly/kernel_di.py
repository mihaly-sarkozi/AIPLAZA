"""Kernel DI wiring: ``configure_kernel_dependencies`` egy helyen."""
from __future__ import annotations

from core.di import configure_kernel_dependencies
from core.platform.bootstrap.infrastructure import InfrastructureRegistry
from core.platform.permissions import PermissionService


def wire_kernel_dependencies(
    *,
    audit_service: object,
    token_service: object,
    login_service: object,
    refresh_service: object,
    logout_service: object,
    permission_service: PermissionService,
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
