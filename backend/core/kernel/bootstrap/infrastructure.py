# backend/core/kernel/bootstrap/infrastructure.py
# Feladat: Felépíti a runtime infrastruktúra példányait egy InfrastructureRegistry-be. Itt jön létre a DB session factory, az email service és a core repository példányok közös registryje, amelyet az AppContainer és a standalone worker entrypoint használ. Core keretrendszer-elem, mert általános infrastruktúra-összeszerelést végez, nem üzleti use case-t.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from core.infrastructure.audit.repositories.audit_log_repository import AuditLogRepository
from core.infrastructure.email.email_service import EmailService
from core.kernel.config.config_loader import settings
from core.kernel.bootstrap.infrastructure_registry import InfrastructureRegistry
from core.kernel.bootstrap.repository_registry import RepositoryRegistry
from core.kernel.db.session import make_session_factory
from core.modules.auth.repository.persistence import (
    Pending2FARepository,
    SessionRepository,
    TwoFactorAttemptRepository,
    TwoFactorRepository,
    UserAuthenticatorRepository,
)
from core.modules.tenant.repositories import TenantRepository
from core.modules.users.repository.persistence import InviteTokenRepository, UserRepository


def build_infrastructure() -> InfrastructureRegistry:
    db_session_factory = make_session_factory(
        settings.database_url,
        pool_pre_ping=getattr(settings, "database_pool_pre_ping", True),
    )

    repositories = RepositoryRegistry(
        tenant_repo=TenantRepository(db_session_factory),
        user_repo=UserRepository(db_session_factory),
        session_repo=SessionRepository(db_session_factory),
        audit_repo=AuditLogRepository(db_session_factory),
        two_factor_repo=TwoFactorRepository(db_session_factory),
        two_factor_attempt_repo=TwoFactorAttemptRepository(db_session_factory),
        pending_2fa_repo=Pending2FARepository(db_session_factory),
        invite_token_repo=InviteTokenRepository(db_session_factory),
        user_authenticator_repo=UserAuthenticatorRepository(db_session_factory),
    )

    return InfrastructureRegistry(
        db_session_factory=db_session_factory,
        email_service=EmailService(),
        repositories=repositories,
    )


__all__ = ["build_infrastructure"]
