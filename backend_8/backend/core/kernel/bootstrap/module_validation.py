# backend/core/kernel/bootstrap/module_validation.py
# Feladat: A modulregisztráció dependency szabályait ellenőrzi. Megakadályozza, hogy core modul kötelező app-szintű service függőséget deklaráljon, és ellenőrzi, hogy a kötelező dependencyk elérhetők-e a ModuleContextben. A module_phases.py használja, ezért ez a moduláris kernel boundary szabályainak általános validációs rétege.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

import logging

from core.kernel.interface.base_app_module import BaseAppModule
from core.kernel.interface.module_context import ModuleContext

_log = logging.getLogger(__name__)


def validate_core_module_deps(module: BaseAppModule) -> None:
    for key in module.service_dependencies():
        if key.startswith("module."):
            raise RuntimeError(
                f"Architektúra sértés: core modul '{module.key}' "
                f"app-szintű (module.*) kötelező függőséget deklarál: {key!r}. "
                "Core modulok csak platform.* service-ektől függhetnek. "
                "Opcionális app-service hozzáféréshez lazy callable mintát használj "
                "a register()-ben (container.get_optional_service()), "
                "optional_service_dependencies()-ben csak platform.* kulcsot adj meg."
            )
    for key in module.optional_service_dependencies():
        if key.startswith("module."):
            _log.warning(
                "Core modul '%s' optional_service_dependencies()-ben app-szintű "
                "kulcsot deklarál: %r. "
                "Core modulok ne hivatkozzanak module.* kulcsokra – "
                "a lazy callable minta a register()-ben elegendő.",
                module.key, key,
            )


def validate_required_deps(module: BaseAppModule, module_context: ModuleContext) -> None:
    missing = tuple(
        name for name in module.service_dependencies()
        if not module_context.has_service(name)
    )
    if missing:
        raise RuntimeError(
            f"Modul '{module.key}' feloldatlan kötelező service dependenciákkal rendelkezik: "
            f"{', '.join(missing)}. "
            "Ellenőrizd a regisztrációs sorrendet és a service_dependencies() deklarációt."
        )


def log_optional_dep_status(module: BaseAppModule, module_context: ModuleContext) -> None:
    for key in module.optional_service_dependencies():
        if not module_context.has_service(key):
            _log.debug(
                "Opcionális service '%s' nem érhető el '%s' modulhoz "
                "(a funkció korlátozott lesz).",
                key, module.key,
            )


__all__ = [
    "log_optional_dep_status",
    "validate_core_module_deps",
    "validate_required_deps",
]
