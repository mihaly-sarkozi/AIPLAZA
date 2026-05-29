# backend/admin/web/schemas/platform_admin_schemas.py
# Feladat: A platform-admin HTTP API Pydantic request és response modelljeit definiálja. Lefedi a login, user management, tenant statisztika, security monitoring, demo signup gate, jelszó, token validation, MFA és IP ban payloadokat. Admin web schema réteg, amelyet az admin_router használ.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class PlatformAdminUserResponse(BaseModel):
    id: int
    email: str
    name: str | None = None
    role: str = "admin"
    is_active: bool = True
    created_at: datetime | None = None
    deleted_at: datetime | None = None
    pending_registration: bool = False
    mfa_enabled: bool = False


class PlatformAdminLoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=200)
    mfa_code: str | None = Field(default=None, min_length=6, max_length=32)


class PlatformAdminLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: PlatformAdminUserResponse


class PlatformAdminTenantResponse(BaseModel):
    id: int
    slug: str
    name: str
    is_active: bool = True
    created_at: datetime | None = None


class PlatformAdminTenantActionRequest(BaseModel):
    confirm_name: str = Field(min_length=1, max_length=255)


class PlatformAdminStatisticsResponse(BaseModel):
    summary: dict
    tenants: list[dict]


class PlatformAdminAuditTrailItem(BaseModel):
    id: int
    created_at: datetime
    user_id: int | None = None
    actor_user_id: int | None = None
    actor_type: str
    action: str
    event_name: str | None = None
    outcome: str | None = None
    target_type: str | None = None
    target_id: str | None = None
    correlation_id: str | None = None
    details: dict = Field(default_factory=dict)
    ip: str | None = None
    user_agent: str | None = None
    actor_email: str | None = None
    actor_email_masked: str | None = None
    actor_email_hash: str | None = None
    actor_name: str | None = None
    target_user_email_masked: str | None = None
    target_user_name: str | None = None
    target_user_settings: dict | None = None
    title: str
    summary: str


class PlatformAdminAuditTrailResponse(BaseModel):
    items: list[PlatformAdminAuditTrailItem]
    limit: int
    next_cursor: str | None = None
    tenant: dict


class PlatformAdminSecurityMonitoringResponse(BaseModel):
    summary: dict
    metrics_summary: dict
    events: list[dict]
    alerts: list[dict]
    tenant_hotspots: list[dict]
    attack_signals: list[dict]
    top_sources: list[dict]
    signup_watch: dict
    duplicate_users: list[dict]
    concurrent_ip_anomalies: list[dict]
    banned_ips: list[dict]
    ai_assessment: str
    event_stream_summary: list[dict]
    alert_rule_results: list[dict]
    monitoring_metrics: list[dict]
    mvp_readiness: dict
    dashboards: list[dict]


class PlatformAdminDebugDateRequest(BaseModel):
    simulated_date: str | None = None


class PlatformAdminDebugDateResponse(BaseModel):
    enabled: bool
    simulated_date: str | None = None
    current_date: str


class PlatformAdminBanIpRequest(BaseModel):
    ip: str = Field(min_length=3, max_length=64)
    reason: str | None = Field(default=None, max_length=255)
    expires_hours: int | None = Field(default=None, ge=1, le=24 * 365)


class PlatformAdminBanIpResponse(BaseModel):
    ip: str
    reason: str | None = None
    created_at: datetime | None = None
    expires_at: datetime | None = None
    active: bool = True


class PlatformAdminAckAlertResponse(BaseModel):
    id: int
    status: str
    acknowledged_at: datetime | None = None
    acknowledged_by: int | None = None


class PlatformAdminDemoSignupGateResponse(BaseModel):
    enabled: bool


class PlatformAdminDemoSignupGateUpdateRequest(BaseModel):
    enabled: bool


class PlatformAdminCreateUserRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    name: str = Field(min_length=1, max_length=100)


class PlatformAdminUpdateUserRequest(BaseModel):
    email: str | None = Field(default=None, min_length=3, max_length=255)
    name: str | None = Field(default=None, min_length=1, max_length=100)
    is_active: bool | None = None


class PlatformAdminProfileUpdateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class PlatformAdminChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=200)
    new_password: str = Field(min_length=1, max_length=200)


class PlatformAdminSetPasswordRequest(BaseModel):
    token: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=200)


class PlatformAdminTokenValidationResponse(BaseModel):
    valid: bool


class PlatformAdminMfaStatusResponse(BaseModel):
    enabled: bool
    pending: bool
    recovery_codes_remaining: int = 0


class PlatformAdminMfaSetupResponse(BaseModel):
    enabled: bool
    pending: bool
    secret: str
    otpauth_uri: str
    expires_at: str


class PlatformAdminMfaConfirmRequest(BaseModel):
    code: str = Field(min_length=6, max_length=32)


class PlatformAdminMfaConfirmResponse(BaseModel):
    enabled: bool
    pending: bool
    recovery_codes: list[str]


class PlatformAdminMfaDisableRequest(BaseModel):
    password: str = Field(min_length=1, max_length=200)

