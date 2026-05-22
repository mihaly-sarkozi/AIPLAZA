# backend/core/kernel/bootstrap/repository_registry.py
# Feladat: A core repository példányokat összefogó RepositoryRegistry adatstruktúrát definiálja. Az infrastructure builder tölti fel konkrét repositorykkal, majd az AppContainer, security réteg és core modulok ezen keresztül kapnak egységes hozzáférést a perzisztencia adapterekhez. Core elem, mert a repositoryk átadásának általános szerződését adja.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from dataclasses import dataclass

from core.infrastructure.audit.repositories.audit_log_repository import AuditLogRepository
from core.modules.auth.repository.persistence import (
    Pending2FARepository,
    SessionRepository,
    TwoFactorAttemptRepository,
    TwoFactorRepository,
    UserAuthenticatorRepository,
)
from core.modules.tenant.repositories import TenantRepository
from core.modules.users.repository.persistence import InviteTokenRepository, UserRepository


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


__all__ = ["RepositoryRegistry"]
