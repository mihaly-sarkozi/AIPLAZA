# backend/core/kernel/bootstrap/modules.py
# Feladat: A manifestben deklarált core és app modulok regisztrációs orchestrátora. Létrehozza a ModuleContextet, publikálja a platform clock service-t, majd szigorú sorrendben futtatja a core és app modul regisztrációs fázisokat. Az AppContainer a runtime felépítésekor használja, ezért ez a moduláris keretrendszer központi bootstrap szerződése.
# Sárközi Mihály - 2026.05.21

"""Core modul regisztrációs motor.

Kétfázisú, szigorú sorrendű modul regisztrációt valósít meg:

  Phase 1 – Core: kernel → core modulok
             Minden core modulnak csak platform.* service kulcsoktól
             szabad függenie (sem module.*, sem belső app-szintű kulcstól).

  Phase 2 – App: core → app modulok
             App modulok az összes core service-t felhasználhatják.
             module.* kulcsú service-ek csak app-app függésekre valók,
             ezeket optional_service_dependencies()-ben kell jelölni.

Sorrend-invariáns: Core modulok MINDIG az app modulok előtt regisztrálódnak.
Ez statikusan kényszerített – a függvény nem fogad el vegyes listát.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

# Nehéz infrastruktúra-függőségek (SQLAlchemy, Pydantic) csak TYPE_CHECKING
# alatt vannak importálva, hogy a pure validációs logika teszteléskor
# ne húzzon be ORM-et vagy config-betöltőt.
if TYPE_CHECKING:
    from core.infrastructure.audit.service.audit_service import AuditService
    from core.kernel.bootstrap.infrastructure_registry import InfrastructureRegistry
    from core.kernel.bootstrap.security import SecurityRegistry

from core.kernel.interface.base_app_module import BaseAppModule
from core.kernel.interface.module_context import ModuleContext
from core.kernel.app.app_manifest import AppManifest
from core.kernel.bootstrap.module_phases import (
    log_all_optional_dep_status,
    register_app_modules,
    register_core_modules,
)
from core.kernel.interface.keys import PLATFORM_CLOCK_SERVICE
from core.kernel.deps.facade import (
    register_factory as register_kernel_factory,
    register_repository as register_kernel_repository,
    register_service as register_kernel_service,
)

_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class ModuleRegistry:
    audit_service: "AuditService"
    module_context: ModuleContext


# ---------------------------------------------------------------------------
# Fő regisztrációs belépési pont
# ---------------------------------------------------------------------------

def register_manifest_modules(
    *,
    infra: "InfrastructureRegistry",
    security: "SecurityRegistry",
    audit_service: "AuditService",
    manifest: AppManifest,
    initial_state: dict | None = None,
) -> ModuleRegistry:
    """Modulokat regisztrálja szigorúan kétfázisú sorrendben: core → app.

    INVARIÁNS: Core modulok MINDIG az app modulok előtt regisztrálódnak.

    Phase 1 – Core modulok
    ----------------------
    A manifest.core_modules listájában lévő összes modul ebben a fázisban
    fut. Core modul csak platform.* service-től függhet (sem module.*,
    sem app-szintű kulcstól).

    Phase 2 – App modulok
    ---------------------
    A manifest.app_modules listájában lévő összes modul a teljes core
    service-készletre építhet. App modulok hivatkozhatnak platform.* és
    module.* kulcsokra egyaránt.

    Sorrend kényszer
    ----------------
    Ez a függvény sosem kezel vegyes sorrendű listát – a manifest.core_modules
    és manifest.app_modules kötelezően elkülönített listák.
    """
    module_context = ModuleContext(
        infrastructure=infra,
        security=security,
        audit_service=audit_service,
        service_publisher=register_kernel_service,
        repository_publisher=register_kernel_repository,
        factory_publisher=register_kernel_factory,
    )
    if initial_state:
        for k, v in initial_state.items():
            module_context.set_state(k, v)

    # A kernel clock mindig az első elérhető core service.
    module_context.register_service(PLATFORM_CLOCK_SERVICE, security.clock)

    # -----------------------------------------------------------------------
    # Phase 1: Core modul regisztráció
    # Invariáns: core modulok előbb futnak, mint bármely app modul.
    # -----------------------------------------------------------------------
    register_core_modules(manifest.core_modules, module_context)

    # -----------------------------------------------------------------------
    # Fázishatár: itt az összes core service rendelkezésre áll.
    # App modulok ettől a ponttól biztonságosan hivatkozhatnak platform.*-ra.
    # -----------------------------------------------------------------------

    # -----------------------------------------------------------------------
    # Phase 2: App modul regisztráció
    # App modulok a teljes core service-készletre építhetnek.
    # -----------------------------------------------------------------------
    register_app_modules(manifest.app_modules, module_context)

    # -----------------------------------------------------------------------
    # Post-regisztráció: opcionális dependenciák feloldottsági log
    # -----------------------------------------------------------------------
    log_all_optional_dep_status(manifest.core_modules + manifest.app_modules, module_context)

    _log.info(
        "Modul regisztráció kész: %d core + %d app modul "
        "(%d service, %d repository, %d factory regisztrálva).",
        len(manifest.core_modules), len(manifest.app_modules),
        len(module_context.services),
        len(module_context.repositories),
        len(module_context.factories),
    )

    return ModuleRegistry(  # type: ignore[arg-type]
        audit_service=audit_service,
        module_context=module_context,
    )
