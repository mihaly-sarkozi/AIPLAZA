# Audit események típusai konstansként.
# 2026.03.25 - Sárközi Mihály

from __future__ import annotations

from enum import StrEnum


class AuditLogAction(StrEnum):
    BRAND_UPDATED = "brand_updated" # Platform brand beállítás változott
    FORGOT_PASSWORD_LINK_SENT = "forgot_password_link_sent" # Jelszó visszaállítási link küldése
    INVITE_RESENT = "invite_resent" # Meghívó link küldése
    LOGIN_2FA_FAILED = "login_2fa_failed" # 2FA sikertelen
    LOGIN_2FA_RATE_LIMITED = "login_2fa_rate_limited" # 2FA ráta limitelt
    LOGIN_2FA_REQUIRED = "login_2fa_required" # 2FA szükséges
    LOGIN_FAILED = "login_failed" # Belépés sikertelen
    LOGIN_SUCCESS = "login_success" # Belépés sikeres
    LOGOUT = "logout" # Kilépés
    LOGOUT_ERROR = "logout_error" # Kilépés hiba
    LOGOUT_FAILED = "logout_failed" # Kilépés sikertelen
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
