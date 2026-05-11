from __future__ import annotations

from dataclasses import dataclass

from core.capabilities.auth.repositories import (
    Pending2FARepository,
    SessionRepository,
    TwoFactorAttemptRepository,
    TwoFactorRepository,
    UserAuthenticatorRepository,
)
from core.capabilities.audit.repositories.audit_log_repository import AuditLogRepository
from core.capabilities.email.email_service import EmailService
from core.capabilities.users.repositories import InviteTokenRepository, UserRepository
from core.extensions.tenant.repositories import TenantRepository
from core.kernel.config.config_loader import settings
from core.kernel.db.session import make_session_factory


@dataclass(frozen=True)
class RepositoryRegistry:
    tenant_repo: TenantRepository
    user_repo: UserRepository
    session_repo: SessionRepository
    audit_repo: AuditLogRepository
    two_factor_repo: TwoFactorRepository
    two_factor_attempt_repo: TwoFactorAttemptRepository
    pending_2fa_repo: Pending2FARepository
    invite_token_repo: InviteTokenRepository
    user_authenticator_repo: UserAuthenticatorRepository


@dataclass(frozen=True)
class InfrastructureRegistry:
    db_session_factory: object
    email_service: EmailService
    repositories: RepositoryRegistry


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
