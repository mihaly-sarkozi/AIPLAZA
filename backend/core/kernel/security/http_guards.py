# backend/core/kernel/security/http_guards.py
# Feladat: HTTP edge security konfigurációkat validál production indulás előtt. Ellenőrzi, hogy CSRF nincs letiltva, trusted_hosts explicit és nem wildcard, valamint tenant_base_domain alkalmas biztonságos CORS origin regex építésére. Core startup security guard a HTTP peremvédelemhez.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

import os
import re

from core.kernel.config.environment import is_production_env
from core.kernel.security.errors import SecurityConfigError

_CSRF_DISABLED_TRUTHY = frozenset({"1", "true", "yes", "on"})
_CSRF_DISABLE_ALLOWED_ENVS = frozenset({"local", "test"})
_DOMAIN_LABEL_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$")


def validate_csrf_policy(env: str) -> None:
    raw = (os.environ.get("DISABLE_CSRF") or "").strip().lower()
    if raw in _CSRF_DISABLED_TRUTHY:
        if env in _CSRF_DISABLE_ALLOWED_ENVS:
            return
        raise SecurityConfigError(
            f"DISABLE_CSRF csak local/test környezetben engedélyezett (aktuális APP_ENV={env}). "
            "Dev/staging/prod környezetben távolítsd el a változót vagy állítsd üresre."
        )


def validate_trusted_hosts(settings: object, env: str) -> None:
    hosts_raw = (getattr(settings, "trusted_hosts", "") or "").strip()

    if is_production_env(env):
        if not hosts_raw:
            raise SecurityConfigError(
                "trusted_hosts production-ben kötelező. "
                "Példa: trusted_hosts=example.com,api.example.com"
            )
        hosts = [h.strip() for h in hosts_raw.split(",") if h.strip()]
        if "*" in hosts:
            raise SecurityConfigError(
                "Wildcard '*' trusted_hosts production-ben nem engedélyezett. "
                "Add meg az engedélyezett hostokat explicit módon."
            )


def validate_cors_origin_regex_policy(settings: object, env: str) -> None:
    if not is_production_env(env):
        return
    raw_base = str(getattr(settings, "tenant_base_domain", "") or "").strip().lower()
    if not raw_base:
        raise SecurityConfigError(
            "tenant_base_domain production-ben kötelező a CORS origin regex biztonságos építéséhez."
        )
    if raw_base in {"local", "localhost"}:
        raise SecurityConfigError(
            f"tenant_base_domain={raw_base!r} production-ben nem engedélyezett."
        )
    if any(token in raw_base for token in ("*", "/", "\\", ":", " ")):
        raise SecurityConfigError(
            f"tenant_base_domain={raw_base!r} érvénytelen formátumú production-ben."
        )
    labels = [part for part in raw_base.split(".") if part]
    if len(labels) < 2:
        raise SecurityConfigError(
            f"tenant_base_domain={raw_base!r} production-ben teljes domain kell legyen (pl. app.example.com)."
        )
    if any(not _DOMAIN_LABEL_RE.fullmatch(label) for label in labels):
        raise SecurityConfigError(
            f"tenant_base_domain={raw_base!r} nem RFC-kompatibilis hostname formátum."
        )


__all__ = [
    "validate_cors_origin_regex_policy",
    "validate_csrf_policy",
    "validate_trusted_hosts",
]
