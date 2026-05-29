# backend/core/modules/users/domain/policies/profile_policy.py
# Feladat: Felhasználói profil policy helper logikát tartalmaz. Locale és theme normalizálást, effective értékszámítást és demo-mode profil szabályokat ad a profile service/router számára. Users profile policy réteg.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from core.modules.users.domain.dto import User

SUPPORTED_LOCALES = ("hu", "en", "es")
SUPPORTED_THEMES = ("light", "dark")


def normalize_locale(locale: str | None) -> str | None:
    value = str(locale).strip().lower() if locale is not None else None
    if not value:
        return None
    return value if value in SUPPORTED_LOCALES else None


def normalize_theme(theme: str | None) -> str | None:
    value = str(theme).strip().lower() if theme is not None else None
    if not value:
        return None
    return value if value in SUPPORTED_THEMES else None


def effective_locale_theme(user: User, owner: User | None) -> tuple[str, str]:
    locale = getattr(user, "preferred_locale", None) or (getattr(owner, "preferred_locale", None) if owner else None) or "hu"
    theme = getattr(user, "preferred_theme", None) or (getattr(owner, "preferred_theme", None) if owner else None) or "light"
    return (
        locale if locale in SUPPORTED_LOCALES else "hu",
        theme if theme in SUPPORTED_THEMES else "light",
    )


def tenant_demo_mode_enabled(tenant) -> bool:
    return bool(
        tenant
        and getattr(tenant, "config", None)
        and getattr(tenant.config, "feature_flags", None)
        and bool(tenant.config.feature_flags.get("demo_mode"))
    )


def default_owner_settings(owner: User | None) -> dict[str, str]:
    locale = (getattr(owner, "preferred_locale", None) or "hu") if owner else "hu"
    theme = (getattr(owner, "preferred_theme", None) or "light") if owner else "light"
    if locale not in SUPPORTED_LOCALES:
        locale = "hu"
    if theme not in SUPPORTED_THEMES:
        theme = "light"
    return {"locale": locale, "theme": theme}


def build_profile_payload(
    user: User,
    *,
    owner: User | None = None,
    tenant_demo_mode: bool = False,
    tenant_kb_has_training: bool = True,
    include_auth_context: bool = True,
) -> dict[str, object]:
    locale, theme = effective_locale_theme(user, owner)
    payload = {
        "id": user.id,
        "email": getattr(user, "email", "") or "",
        "pending_email": getattr(user, "pending_email", None),
        "pending_email_expires_at": getattr(user, "pending_email_expires_at", None),
        "role": user.role,
        "is_active": bool(getattr(user, "is_active", True)),
        "name": getattr(user, "name", None),
        "preferred_locale": getattr(user, "preferred_locale", None),
        "preferred_theme": getattr(user, "preferred_theme", None),
        "locale": locale,
        "theme": theme,
    }
    if include_auth_context:
        payload["credentials_password_set"] = getattr(user, "credentials_password_set", True)
        payload["tenant_demo_mode"] = tenant_demo_mode
        payload["tenant_kb_has_training"] = tenant_kb_has_training
    return payload


def build_profile_updates(
    *,
    name: str | None,
    preferred_locale: str | None,
    preferred_theme: str | None,
) -> dict[str, object]:
    updates: dict[str, object] = {}
    if name is not None:
        updates["name"] = str(name).strip() or None
    if preferred_locale is not None:
        updates["preferred_locale"] = normalize_locale(preferred_locale)
    if preferred_theme is not None:
        updates["preferred_theme"] = normalize_theme(preferred_theme)
    return updates
