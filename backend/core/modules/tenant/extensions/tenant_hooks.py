# backend/core/modules/tenant/extensions/tenant_hooks.py
# Feladat: Tenant sign-up/provisioning hook registryt tartalmaz app modulok számára. Tenant létrehozás után futtatható extension hookokat gyűjt, listáz és resetel, hogy modulok saját tenant inicializálást kapcsolhassanak a folyamatba. Tenant extension integrációs réteg.
# Sárközi Mihály - 2026.05.21

"""Tenant extension registry – platform hook/port a tenant signup köré.

A core tenant signup orchestration itt keresi meg az opcionálisan regisztrált
app-oldali hookokat. A core nem ismer app modul neveket vagy service kulcsokat.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class TenantSignupContext:
    tenant_slug: str
    tenant_name: str
    tenant_id: int | None
    owner_id: int
    owner_email: str
    locale: str
    plan_code: str
    subscription_period: str
    demo_session_id: str
    is_new_tenant: bool


class TenantSignupHook(Protocol):
    def handle(self, context: TenantSignupContext) -> None: ...


TenantProvisioningHook = TenantSignupHook


class TenantExtensionRegistry:
    """Platform-szintű registry tenant extension hookokhoz."""

    def __init__(self) -> None:
        self._tenant_signup_hooks: dict[str, TenantSignupHook] = {}

    def register_tenant_signup_hook(self, name: str, hook: TenantSignupHook) -> None:
        normalized = (name or "").strip()
        if not normalized:
            raise ValueError("tenant signup hook name must not be empty")
        self._tenant_signup_hooks[normalized] = hook

    def get_tenant_signup_hooks(self) -> tuple[TenantSignupHook, ...]:
        return tuple(self._tenant_signup_hooks.values())

    def clear(self) -> None:
        self._tenant_signup_hooks.clear()


_registry = TenantExtensionRegistry()


def register_tenant_signup_hook(name: str, hook: TenantSignupHook) -> None:
    _registry.register_tenant_signup_hook(name, hook)


def get_tenant_signup_hooks() -> tuple[TenantSignupHook, ...]:
    return _registry.get_tenant_signup_hooks()


def clear_tenant_signup_hooks() -> None:
    _registry.clear()


def get_tenant_extension_registry() -> TenantExtensionRegistry:
    return _registry


__all__ = [
    "TenantExtensionRegistry",
    "TenantProvisioningHook",
    "TenantSignupContext",
    "TenantSignupHook",
    "clear_tenant_signup_hooks",
    "get_tenant_extension_registry",
    "get_tenant_signup_hooks",
    "register_tenant_signup_hook",
]

