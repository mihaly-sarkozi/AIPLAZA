# backend/core/infrastructure/audit/const/audit_log_action_const.py
# Feladat: A platform audit naplózás stabil action enumját definiálja. Auth, 2FA, refresh/logout, users, settings, brand, tenant provisioning, platform admin és knowledge PII események közös névterét adja. Audit contract réteg, amelyet service-ek és tesztek is importálnak.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from enum import StrEnum


class AuditLogAction(StrEnum):
    BRAND_UPDATED = "brand_updated" # Platform brand beállítás változott
    FORGOT_PASSWORD_LINK_SENT = "forgot_password_link_sent" # Jelszó visszaállítási link küldése
    EMAIL_CONFIRMED = "email_confirmed" # Email megerősítő link sikeres jóváhagyása
    INVITE_RESENT = "invite_resent" # Meghívó link küldése
    LOGIN_2FA_FAILED = "login_2fa_failed" # 2FA sikertelen
    LOGIN_2FA_RATE_LIMITED = "login_2fa_rate_limited" # 2FA ráta limitelt
    LOGIN_2FA_REQUIRED = "login_2fa_required" # 2FA szükséges
    LOGIN_2FA_SUCCESS = "login_2fa_success" # 2FA sikeres
    LOGIN_FAILED = "login_failed" # Belépés sikertelen
    LOGIN_SUCCESS = "login_success" # Belépés sikeres
    LOGOUT = "logout" # Kilépés
    LOGOUT_ERROR = "logout_error" # Kilépés hiba
    LOGOUT_FAILED = "logout_failed" # Kilépés sikertelen
    PASSWORD_CHANGED = "password_changed" # Felhasználó jelszót módosított
    PASSWORD_SET_BY_INVITE = "password_set_by_invite" # Jelszó beállítása meghívóval
    REFRESH = "refresh" # Token frissítése  
    REFRESH_FAILED = "refresh_failed" # Token frissítés sikertelen
    REFRESH_SUSPICIOUS_FINGERPRINT = "refresh_suspicious_fingerprint" # Frissítés gyanús kézjegy
    SETTINGS_SECURITY_UPDATED = "settings_security_updated" # Security-sensitive platform setting változott
    TENANT_PROVISIONED = "tenant_provisioned" # Tenant provisioning sikeres
    USER_CREATED = "user_created" # Felhasználó létrehozása
    USER_DELETED = "user_deleted" # Felhasználó törlése
    USER_EMAIL_CHANGED = "user_email_changed" # Felhasználó email címének módosítása
    USER_ROLE_CHANGED = "user_role_changed" # Felhasználó szerepkörének módosítása
    USER_UPDATED = "user_updated" # Felhasználó módosítása
    PLATFORM_ADMIN_LOGIN_SUCCESS = "platform_admin_login_success"
    PLATFORM_ADMIN_LOGIN_FAILED = "platform_admin_login_failed"
    PLATFORM_ADMIN_MFA_REQUIRED = "platform_admin_mfa_required"
    PLATFORM_ADMIN_MFA_PASSED = "platform_admin_mfa_passed"
    PLATFORM_ADMIN_MFA_FAILED = "platform_admin_mfa_failed"
    PLATFORM_ADMIN_REFRESH = "platform_admin_refresh"
    PLATFORM_ADMIN_REFRESH_FAILED = "platform_admin_refresh_failed"
    PLATFORM_ADMIN_LOGOUT = "platform_admin_logout"
    PLATFORM_ADMIN_PROFILE_UPDATED = "platform_admin_profile_updated"
    PLATFORM_ADMIN_PASSWORD_CHANGED = "platform_admin_password_changed"
    PLATFORM_ADMIN_STATS_VIEWED = "platform_admin_stats_viewed"
    PLATFORM_ADMIN_TENANT_STATS_VIEWED = "platform_admin_tenant_stats_viewed"
    PLATFORM_ADMIN_SECURITY_IP_BANNED = "platform_admin_security_ip_banned"
    PLATFORM_ADMIN_SECURITY_IP_UNBANNED = "platform_admin_security_ip_unbanned"
    PLATFORM_ADMIN_SECURITY_ALERT_ACK = "platform_admin_security_alert_ack"
    INTERNAL_ENDPOINT_ACCESSED = "internal_endpoint_accessed"
    ADMIN_ACTION = "admin_action"
    PERMISSION_DENIED = "permission_denied"
    KNOWLEDGE_PII_DEPERSONALIZED = "knowledge_pii_depersonalized"
    KNOWLEDGE_CREATED = "knowledge_created"
    KNOWLEDGE_DELETED = "knowledge_deleted"
    KNOWLEDGE_PERMISSION_CHANGED = "knowledge_permission_changed"
    KNOWLEDGE_SETTING_CHANGED = "knowledge_setting_changed"
    KNOWLEDGE_TRAINING_STARTED = "knowledge_training_started"
    KNOWLEDGE_SOURCE_DELETED = "knowledge_source_deleted"
    KNOWLEDGE_URL_INGEST_REJECTED = "knowledge_url_ingest_rejected"
    KNOWLEDGE_UPLOAD_REJECTED = "knowledge_upload_rejected"
    API_CREDENTIAL_CREATED = "api_credential_created"
    API_CREDENTIAL_ROTATED = "api_credential_rotated"
    API_CREDENTIAL_REVOKED = "api_credential_revoked"
    SIGNED_REQUEST_REJECTED = "signed_request_rejected"
