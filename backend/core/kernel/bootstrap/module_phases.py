# backend/core/kernel/bootstrap/module_phases.py
# Feladat: A modulregisztráció core és app fázisainak végrehajtó helperjeit tartalmazza. A modules.py hívja, hogy a fázisok futtatása, logolása és opcionális dependency státuszjelentése elkülönüljön az orchestrátor API-tól. Core elem, mert általános moduláris bootstrap folyamatot valósít meg.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

import logging

from core.kernel.bootstrap.module_validation import (
    log_optional_dep_status,
    validate_core_module_deps,
    validate_required_deps,
)
from core.kernel.interface.base_app_module import BaseAppModule
from core.kernel.interface.module_context import ModuleContext

_log = logging.getLogger(__name__)


def register_core_modules(modules: list[BaseAppModule], module_context: ModuleContext) -> None:
    n_core = len(modules)
    _log.info("Modul regisztráció – 1. fázis: %d core modul", n_core)

    for module in modules:
        validate_core_module_deps(module)
        validate_required_deps(module, module_context)
        module.register(module_context)
        _log.debug("  [core] regisztrálva: %s", module.key)

    _log.info(
        "Modul regisztráció – 1. fázis befejezve: %d core service elérhető.",
        len(module_context.services),
    )


def register_app_modules(modules: list[BaseAppModule], module_context: ModuleContext) -> None:
    n_app = len(modules)
    _log.info("Modul regisztráció – 2. fázis: %d app modul", n_app)

    for module in modules:
        validate_required_deps(module, module_context)
        module.register(module_context)
        _log.debug("  [app] regisztrálva: %s", module.key)


def log_all_optional_dep_status(modules: list[BaseAppModule], module_context: ModuleContext) -> None:
    for module in modules:
        log_optional_dep_status(module, module_context)


__all__ = [
    "log_all_optional_dep_status",
    "register_app_modules",
    "register_core_modules",
]
