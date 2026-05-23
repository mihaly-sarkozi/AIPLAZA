# backend/admin/web/schemas/__init__.py
# Feladat: A platform-admin HTTP request/response sémák exportfelülete. A router által használt Pydantic modelleket egy helyről teszi importálhatóvá login, MFA, user management, monitoring, alert és IP ban endpointokhoz. Admin web schema csomagbelépő.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from .platform_admin_schemas import (
    PlatformAdminAckAlertResponse,
    PlatformAdminBanIpRequest,
    PlatformAdminBanIpResponse,
    PlatformAdminChangePasswordRequest,
    PlatformAdminCreateUserRequest,
    PlatformAdminDemoSignupGateResponse,
    PlatformAdminDemoSignupGateUpdateRequest,
    PlatformAdminLoginRequest,
    PlatformAdminLoginResponse,
    PlatformAdminMfaConfirmRequest,
    PlatformAdminMfaConfirmResponse,
    PlatformAdminMfaDisableRequest,
    PlatformAdminMfaSetupResponse,
    PlatformAdminMfaStatusResponse,
    PlatformAdminProfileUpdateRequest,
    PlatformAdminSecurityMonitoringResponse,
    PlatformAdminSetPasswordRequest,
    PlatformAdminStatisticsResponse,
    PlatformAdminTenantResponse,
    PlatformAdminTokenValidationResponse,
    PlatformAdminUpdateUserRequest,
    PlatformAdminUserResponse,
)

__all__ = [
    "PlatformAdminAckAlertResponse",
    "PlatformAdminBanIpRequest",
    "PlatformAdminBanIpResponse",
    "PlatformAdminChangePasswordRequest",
    "PlatformAdminCreateUserRequest",
    "PlatformAdminDemoSignupGateResponse",
    "PlatformAdminDemoSignupGateUpdateRequest",
    "PlatformAdminLoginRequest",
    "PlatformAdminLoginResponse",
    "PlatformAdminMfaConfirmRequest",
    "PlatformAdminMfaConfirmResponse",
    "PlatformAdminMfaDisableRequest",
    "PlatformAdminMfaSetupResponse",
    "PlatformAdminMfaStatusResponse",
    "PlatformAdminProfileUpdateRequest",
    "PlatformAdminSecurityMonitoringResponse",
    "PlatformAdminSetPasswordRequest",
    "PlatformAdminStatisticsResponse",
    "PlatformAdminTenantResponse",
    "PlatformAdminTokenValidationResponse",
    "PlatformAdminUpdateUserRequest",
    "PlatformAdminUserResponse",
]
