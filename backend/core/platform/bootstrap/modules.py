"""Platform modul regisztrációs motor.

Kétfázisú, szigorú sorrendű modul regisztrációt valósít meg:

  Phase 1 – Platform: kernel → platform modulok
             Minden platform modulnak csak platform.* service kulcsoktól
             szabad függenie (sem module.*, sem belső app-szintű kulcstól).

  Phase 2 – App: platform → app modulok
             App modulok az összes platform service-t felhasználhatják.
             module.* kulcsú service-ek csak app-app függésekre valók,
             ezeket optional_service_dependencies()-ben kell jelölni.

Sorrend-invariáns: Platform modulok MINDIG az app modulok előtt regisztrálódnak.
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
    from core.capabilities.audit.service.audit_service import AuditService
    from core.platform.bootstrap.infrastructure import InfrastructureRegistry
    from core.platform.bootstrap.security import SecurityRegistry

from core.platform.composition import AppModule, ModuleContext
from core.platform.manifest import PlatformManifest
from core.platform.service_keys import PLATFORM_CLOCK_SERVICE

_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class ModuleRegistry:
    audit_service: "AuditService"
    module_context: ModuleContext


# ---------------------------------------------------------------------------
# Validációs segédfüggvények
# ---------------------------------------------------------------------------

def _is_platform_module(module: AppModule) -> bool:
    """Platform modul-e? Konvenció: key = 'platform.*'"""
    return str(getattr(module, "key", "") or "").startswith("platform.")


def _is_app_module(module: AppModule) -> bool:
    """App modul-e? Konvenció: key = 'app.*'"""
    return str(getattr(module, "key", "") or "").startswith("app.")


def _validate_platform_module_deps(module: AppModule) -> None:
    """Platform modul required service_dependencies()-e CSAK platform.* kulcsokat tartalmazhat.

    module.* kulcs (app-szintű) platform modul required dep-jében = architektúra sértés.
    optional_service_dependencies()-ben is csak platform.* kulcs fogadható el platform modulban.
    """
    for key in module.service_dependencies():
        if key.startswith("module."):
            raise RuntimeError(
                f"Architektúra sértés: platform modul '{module.key}' "
                f"app-szintű (module.*) kötelező függőséget deklarál: {key!r}. "
                "Platform modulok csak platform.* service-ektől függhetnek. "
                "Opcionális app-service hozzáféréshez lazy callable mintát használj "
                "a register()-ben (container.get_optional_service()), "
                "optional_service_dependencies()-ben csak platform.* kulcsot adj meg."
            )
    for key in module.optional_service_dependencies():
        if key.startswith("module."):
            _log.warning(
                "Platform modul '%s' optional_service_dependencies()-ben app-szintű "
                "kulcsot deklarál: %r. "
                "Platform modulok ne hivatkozzanak module.* kulcsokra – "
                "a lazy callable minta a register()-ben elegendő.",
                module.key, key,
            )


def _validate_required_deps(module: AppModule, module_context: ModuleContext) -> None:
    """Ellenőrzi, hogy a modul összes kötelező service dependency elérhető-e."""
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


def _log_optional_dep_status(module: AppModule, module_context: ModuleContext) -> None:
    """Post-regisztrációs log: opcionális service-ek feloldottak-e."""
    for key in module.optional_service_dependencies():
        if not module_context.has_service(key):
            _log.debug(
                "Opcionális service '%s' nem érhető el '%s' modulhoz "
                "(a funkció korlátozott lesz).",
                key, module.key,
            )


# ---------------------------------------------------------------------------
# Fő regisztrációs belépési pont
# ---------------------------------------------------------------------------

def register_manifest_modules(
    *,
    infra: "InfrastructureRegistry",
    security: "SecurityRegistry",
    audit_service: "AuditService",
    manifest: PlatformManifest,
    initial_state: dict | None = None,
) -> ModuleRegistry:
    """Modulokat regisztrálja szigorúan kétfázisú sorrendben: platform → app.

    INVARIÁNS: Platform modulok MINDIG az app modulok előtt regisztrálódnak.

    Phase 1 – Platform modulok
    --------------------------
    A manifest.platform_modules listájában lévő összes modul ebben a fázisban
    fut. Platform modul csak platform.* service-től függhet (sem module.*,
    sem app-szintű kulcstól).

    Phase 2 – App modulok
    ---------------------
    A manifest.app_modules listájában lévő összes modul a teljes platform
    service-készletre építhet. App modulok hivatkozhatnak platform.* és
    module.* kulcsokra egyaránt.

    Sorrend kényszer
    ----------------
    Ez a függvény sosem kezel vegyes sorrendű listát – a manifest.platform_modules
    és manifest.app_modules kötelezően elkülönített listák.
    """
    module_context = ModuleContext(
        infrastructure=infra,
        security=security,
        audit_service=audit_service,
    )
    if initial_state:
        for k, v in initial_state.items():
            module_context.set_state(k, v)

    # A kernel clock mindig az első elérhető platform service.
    module_context.register_service(PLATFORM_CLOCK_SERVICE, security.clock)

    # -----------------------------------------------------------------------
    # Phase 1: Platform modul regisztráció
    # Invariáns: platform modulok előbb futnak, mint bármely app modul.
    # -----------------------------------------------------------------------
    n_platform = len(manifest.platform_modules)
    _log.info(
        "Modul regisztráció – 1. fázis: %d platform modul",
        n_platform,
    )

    for module in manifest.platform_modules:
        # Kötelező: platform modulok nem hivatkozhatnak app-szintű kulcsokra.
        _validate_platform_module_deps(module)
        # Kötelező: platform.* service dependenciák mind elérhetők.
        _validate_required_deps(module, module_context)
        module.register(module_context)
        _log.debug("  [platform] regisztrálva: %s", module.key)

    _log.info(
        "Modul regisztráció – 1. fázis befejezve: %d platform service elérhető.",
        len(module_context.services),
    )

    # -----------------------------------------------------------------------
    # Fázishatár: itt az összes platform service rendelkezésre áll.
    # App modulok ettől a ponttól biztonságosan hivatkozhatnak platform.*-ra.
    # -----------------------------------------------------------------------

    # -----------------------------------------------------------------------
    # Phase 2: App modul regisztráció
    # App modulok a teljes platform service-készletre építhetnek.
    # -----------------------------------------------------------------------
    n_app = len(manifest.app_modules)
    _log.info(
        "Modul regisztráció – 2. fázis: %d app modul",
        n_app,
    )

    for module in manifest.app_modules:
        _validate_required_deps(module, module_context)
        module.register(module_context)
        _log.debug("  [app] regisztrálva: %s", module.key)

    # -----------------------------------------------------------------------
    # Post-regisztráció: opcionális dependenciák feloldottsági log
    # -----------------------------------------------------------------------
    for module in manifest.platform_modules + manifest.app_modules:
        _log_optional_dep_status(module, module_context)

    _log.info(
        "Modul regisztráció kész: %d platform + %d app modul "
        "(%d service, %d repository, %d factory regisztrálva).",
        n_platform, n_app,
        len(module_context.services),
        len(module_context.repositories),
        len(module_context.factories),
    )

    return ModuleRegistry(  # type: ignore[arg-type]
        audit_service=audit_service,
        module_context=module_context,
    )
