# apps/auth/ports/__init__.py – csak authentikációhoz tartozó portok
from apps.auth.ports.tenant_repository_interface import TenantRepositoryInterface
from apps.auth.ports.session_repository_interface import SessionRepositoryInterface
from apps.auth.ports.two_factor_repository_interface import TwoFactorRepositoryInterface
from apps.auth.ports.two_factor_attempt_repository_interface import TwoFactorAttemptRepositoryInterface
from apps.auth.ports.pending_2fa_repository_interface import Pending2FARepositoryInterface

__all__ = [
    "TenantRepositoryInterface",
    "SessionRepositoryInterface",
    "TwoFactorRepositoryInterface",
    "TwoFactorAttemptRepositoryInterface",
    "Pending2FARepositoryInterface",
]
