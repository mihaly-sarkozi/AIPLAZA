# backend/core/kernel/interface/keys.py
# Feladat: Platform szintű service kulcsok és typed helper definíciók kanonikus helye. A platform.* névteret egységesíti auth, users, tenant, settings, domain, lifecycle és egyéb core szolgáltatásokhoz. Public core interface, amely DI boundary-kat és service dependency-ket tesz stabilan hivatkozhatóvá.
# Sárközi Mihály - 2026.05.21

"""Platform service key interface.

This module is the canonical source for platform-only service keys and typed
helpers. Keep it lightweight and import-safe.
"""
from __future__ import annotations

import re
from typing import Literal, NewType

ServiceKey = NewType("ServiceKey", str)

_SLUG = re.compile(r"^[a-z][a-z0-9_]*$")

Role = Literal["service", "repository", "factory", "worker"]


def platform_service_key(domain: str, *, role: str = "service") -> ServiceKey:
    """``platform.{domain}.{role}`` alakú kulcs.

    A helper csak a platform saját kulcsaihoz használatos.
    """
    s = (domain or "").strip().lower().replace("-", "_")
    if not _SLUG.fullmatch(s):
        raise ValueError(f"platform_service_key: érvénytelen domain: {domain!r}")
    return ServiceKey(f"platform.{s}.{role}")

# ---------------------------------------------------------------------------
# Clock
# ---------------------------------------------------------------------------

PLATFORM_CLOCK_SERVICE = "platform.clock"

# ---------------------------------------------------------------------------
# Job queue (platform outbox)
# ---------------------------------------------------------------------------

PLATFORM_JOB_QUEUE = "platform.job_queue"

# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

PLATFORM_SETTINGS_SERVICE = "platform.settings.service"
PLATFORM_SETTINGS_REPOSITORY = "platform.settings.repository"

# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

PLATFORM_AUTH_SESSION_REPOSITORY = "platform.auth.session_repository"
PLATFORM_AUTH_TWO_FACTOR_SERVICE = "platform.auth.two_factor_service"
PLATFORM_LOGIN_SERVICE = "platform.login_service"
PLATFORM_REFRESH_SERVICE = "platform.refresh_service"
PLATFORM_LOGOUT_SERVICE = "platform.logout_service"
PLATFORM_ADMIN_SERVICE = "platform.admin.service"

# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

PLATFORM_USERS_SERVICE = "platform.users.service"
PLATFORM_USERS_PROFILE_SERVICE = "platform.users.profile_service"
PLATFORM_USERS_INVITE_SERVICE = "platform.users.invite_service"

# ---------------------------------------------------------------------------
# Tenant
# ---------------------------------------------------------------------------

PLATFORM_TENANT_EXTENSION_REGISTRY_SERVICE = "platform.tenant.extension_registry"
PLATFORM_TENANT_LIFECYCLE_POLICY = "platform.tenant.lifecycle_policy"
PLATFORM_TENANT_SIGNUP_FACTORY = "platform.tenant.signup_service"
PLATFORM_TENANT_USAGE_SERVICE = "platform.tenant.usage_service"

# ---------------------------------------------------------------------------
# Brand
# ---------------------------------------------------------------------------

PLATFORM_BRAND_REPOSITORY = "platform.brand.repository"
PLATFORM_BRAND_SERVICE = "platform.brand.service"

# ---------------------------------------------------------------------------
# Domain
# ---------------------------------------------------------------------------

PLATFORM_DOMAIN_REPOSITORY = "platform.domain.repository"
PLATFORM_DOMAIN_ROUTING_POLICY = "platform.domain.routing_policy"
PLATFORM_DOMAIN_POLICY = "platform.domain.policy"
PLATFORM_DOMAIN_VERIFICATION_SERVICE = "platform.domain.verification_service"
PLATFORM_DOMAIN_SERVICE = "platform.domain.service"

# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------

PLATFORM_LIFECYCLE_SERVICE = "platform.lifecycle.service"

# ---------------------------------------------------------------------------
# Short aliases
# ---------------------------------------------------------------------------

PLATFORM_CLOCK = PLATFORM_CLOCK_SERVICE
PLATFORM_SETTINGS = PLATFORM_SETTINGS_SERVICE
PLATFORM_LOGIN = PLATFORM_LOGIN_SERVICE
PLATFORM_REFRESH = PLATFORM_REFRESH_SERVICE
PLATFORM_LOGOUT = PLATFORM_LOGOUT_SERVICE
PLATFORM_USERS = PLATFORM_USERS_SERVICE
PLATFORM_USERS_PROFILE = PLATFORM_USERS_PROFILE_SERVICE
PLATFORM_USERS_INVITE = PLATFORM_USERS_INVITE_SERVICE
PLATFORM_TENANT_EXTENSION_REGISTRY = PLATFORM_TENANT_EXTENSION_REGISTRY_SERVICE
PLATFORM_TENANT_LIFECYCLE = PLATFORM_TENANT_LIFECYCLE_POLICY
PLATFORM_TENANT_SIGNUP = PLATFORM_TENANT_SIGNUP_FACTORY
PLATFORM_TENANT_USAGE = PLATFORM_TENANT_USAGE_SERVICE
PLATFORM_BRAND = PLATFORM_BRAND_SERVICE
PLATFORM_DOMAIN = PLATFORM_DOMAIN_SERVICE
PLATFORM_DOMAIN_ROUTING = PLATFORM_DOMAIN_ROUTING_POLICY
PLATFORM_LIFECYCLE = PLATFORM_LIFECYCLE_SERVICE

__all__ = [
    "Role",
    "ServiceKey",
    "PLATFORM_AUTH_SESSION_REPOSITORY",
    "PLATFORM_AUTH_TWO_FACTOR_SERVICE",
    "PLATFORM_BRAND",
    "PLATFORM_BRAND_REPOSITORY",
    "PLATFORM_BRAND_SERVICE",
    "PLATFORM_CLOCK",
    "PLATFORM_CLOCK_SERVICE",
    "PLATFORM_DOMAIN",
    "PLATFORM_DOMAIN_POLICY",
    "PLATFORM_DOMAIN_REPOSITORY",
    "PLATFORM_DOMAIN_ROUTING",
    "PLATFORM_DOMAIN_ROUTING_POLICY",
    "PLATFORM_DOMAIN_SERVICE",
    "PLATFORM_DOMAIN_VERIFICATION_SERVICE",
    "PLATFORM_JOB_QUEUE",
    "PLATFORM_LIFECYCLE",
    "PLATFORM_LIFECYCLE_SERVICE",
    "PLATFORM_LOGIN",
    "PLATFORM_LOGIN_SERVICE",
    "PLATFORM_LOGOUT",
    "PLATFORM_LOGOUT_SERVICE",
    "PLATFORM_REFRESH",
    "PLATFORM_REFRESH_SERVICE",
    "PLATFORM_SETTINGS",
    "PLATFORM_SETTINGS_REPOSITORY",
    "PLATFORM_SETTINGS_SERVICE",
    "PLATFORM_TENANT_EXTENSION_REGISTRY",
    "PLATFORM_TENANT_EXTENSION_REGISTRY_SERVICE",
    "PLATFORM_TENANT_LIFECYCLE",
    "PLATFORM_TENANT_LIFECYCLE_POLICY",
    "PLATFORM_TENANT_SIGNUP",
    "PLATFORM_TENANT_SIGNUP_FACTORY",
    "PLATFORM_TENANT_USAGE",
    "PLATFORM_TENANT_USAGE_SERVICE",
    "PLATFORM_USERS",
    "PLATFORM_USERS_INVITE",
    "PLATFORM_USERS_INVITE_SERVICE",
    "PLATFORM_USERS_PROFILE",
    "PLATFORM_USERS_PROFILE_SERVICE",
    "PLATFORM_USERS_SERVICE",
    "platform_service_key",
]

