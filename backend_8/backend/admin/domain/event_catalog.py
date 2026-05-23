# backend/admin/domain/event_catalog.py
# Feladat: A platform admin security monitoring által ismert eseménykatalógust definiálja. Auth, security, business és system eseményeket kategorizál, hogy a monitoring dashboard és alert szabályok egységes névtérből dolgozzanak. Admin domain support adat, nem runtime logika.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

AUTH_EVENTS = (
    "login_success",
    "login_failed",
    "logout",
    "password_reset_requested",
    "password_reset_success",
    "mfa_failed",
    "mfa_success",
    "new_device_login",
    "new_country_login",
)

SECURITY_EVENTS = (
    "rate_limit_triggered",
    "blocked_ip",
    "suspicious_request",
    "invalid_token",
    "expired_token",
    "permission_denied",
    "privilege_escalation_attempt",
    "admin_login",
    "admin_action",
)

BUSINESS_EVENTS = (
    "user_registered",
    "subscription_created",
    "subscription_cancelled",
    "payment_failed",
    "payment_success",
    "workspace_created",
    "export_started",
    "export_completed",
)

SYSTEM_EVENTS = (
    "api_error",
    "db_error",
    "external_api_error",
    "queue_job_failed",
    "background_job_failed",
    "deployment_started",
    "deployment_finished",
)

EVENT_CATEGORIES: dict[str, str] = {
    **{name: "auth" for name in AUTH_EVENTS},
    **{name: "security" for name in SECURITY_EVENTS},
    **{name: "business" for name in BUSINESS_EVENTS},
    **{name: "system" for name in SYSTEM_EVENTS},
}

ALL_MONITORING_EVENTS: tuple[str, ...] = tuple(
    list(AUTH_EVENTS) + list(SECURITY_EVENTS) + list(BUSINESS_EVENTS) + list(SYSTEM_EVENTS)
)
