# backend/core/modules/tenant/schema/hooks.py
# Feladat: Tenant schema hook registryt tartalmaz. Core és app modulok táblatelepítési hookjait gyűjti, listázza és manifestből regisztrálja, hogy tenant schema létrehozáskor minden modul saját táblát telepíthessen. Tenant schema extension registry.
# Sárközi Mihály - 2026.05.21

"""Tenant schema hook registry.

Responsibility: register, list and reset tenant schema migration hooks.
Pure bookkeeping – no DDL execution here.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

from sqlalchemy.engine import Engine

if TYPE_CHECKING:
    from core.kernel.app.app_manifest import AppManifest


@dataclass(frozen=True)
class TenantSchemaHook:
    name: str
    install: Callable[[Engine, str], None]
    table_names: tuple[str, ...] = ()
    revision: str | None = None


_registered_hooks: dict[str, TenantSchemaHook] = {}
_kernel_hooks: tuple[TenantSchemaHook, ...] = ()


def tenant_migration_revision(hook: TenantSchemaHook) -> str:
    return (hook.revision or hook.name).strip()


def register_tenant_schema_hooks(
    hooks: tuple[TenantSchemaHook, ...] | list[TenantSchemaHook],
) -> None:
    for hook in hooks:
        _registered_hooks[tenant_migration_revision(hook)] = hook


def register_manifest_tenant_schema_hooks(manifest: "AppManifest") -> None:
    reset_tenant_schema_hooks()
    for register in manifest.tenant_schema_hooks:
        register()


def reset_tenant_schema_hooks() -> None:
    _registered_hooks.clear()


def list_tenant_schema_hooks() -> tuple[TenantSchemaHook, ...]:
    hooks = list(_kernel_hooks) + list(_registered_hooks.values())
    return tuple(sorted(hooks, key=tenant_migration_revision))


def list_tenant_schema_table_names() -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for hook in list_tenant_schema_hooks():
        for table_name in hook.table_names:
            if table_name not in seen:
                seen.add(table_name)
                names.append(table_name)
    return names


__all__ = [
    "TenantSchemaHook",
    "list_tenant_schema_hooks",
    "list_tenant_schema_table_names",
    "register_manifest_tenant_schema_hooks",
    "register_tenant_schema_hooks",
    "reset_tenant_schema_hooks",
    "tenant_migration_revision",
]
