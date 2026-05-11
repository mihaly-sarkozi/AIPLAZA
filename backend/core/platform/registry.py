"""Platform modul registry – a core platform modulok betöltője.

Ez a fájl határozza meg, hogy mely platform modulok töltődnek be, és
milyen sorrendben regisztrálódnak.

Sorrend-invariáns
=================
A platform modulok egymástól való függőségei alapján rögzített sorrendben
kell regisztrálni őket. A bootstrap/modules.py a service_dependencies()
deklarációk alapján is validálja a sorrendet, de a sorrendet itt kell
helyesen meghatározni.

Jelenlegi sorrend és miért
--------------------------

  1. lifecycle    – nincs platformfüggőség; health/readiness endpoint a legkorábban kell
  2. settings     – nincs platformfüggőség; PLATFORM_SETTINGS_SERVICE szükséges az auth-hoz
  3. users        – nincs platformfüggőség; PLATFORM_USERS_SERVICE szükséges a tenant-hoz
  4. auth         – PLATFORM_SETTINGS_SERVICE, PLATFORM_CLOCK_SERVICE
  5. platform_admin – public sémás főadmin auth és user-kezelés
  6. tenant       – PLATFORM_USERS_SERVICE, PLATFORM_CLOCK_SERVICE
                    (opcionálisan: platform usage service – lazy callable, nem blokkoló)
  7. domain       – PLATFORM_TENANT_LIFECYCLE_POLICY (tenant modul regisztrálja)
  8. brand        – PLATFORM_TENANT_LIFECYCLE_POLICY (tenant modul regisztrálja)

MEGJEGYZÉS: platform modulok CSAK platform.* kulcsoktól függhetnek.
             App-szintű (module.*) kulcsokra platform modul nem hivatkozhat
             service_dependencies()-ben vagy optional_service_dependencies()-ben.
             Opcionális app service-eket a register()-ben lazy callableként kell kezelni.
"""
from __future__ import annotations

from core.platform.manifest import PlatformManifest, build_platform_manifest


def load_core_platform_manifest() -> PlatformManifest:
    """Platform manifest betöltése – kizárólag core platform modulokkal.

    App modulok NEM szerepelnek ebben a manifestben – azokat a composition root
    (main.py) adja hozzá a merge_app_manifest() hívással.

    Sorrend: lifecycle → settings → users → auth → tenant → domain → brand
    """
    from core.platform_modules.auth.module import get_module as get_auth_platform_module
    from core.platform_modules.brand.module import get_module as get_brand_platform_module
    from core.platform_modules.domain.module import get_module as get_domain_platform_module
    from core.platform_modules.lifecycle.module import get_module as get_lifecycle_platform_module
    from core.platform_modules.platform_admin.module import get_module as get_platform_admin_module
    from core.platform_modules.settings.module import get_module as get_settings_platform_module
    from core.platform_modules.tenant.module import get_module as get_tenant_platform_module
    from core.platform_modules.users.module import get_module as get_users_platform_module

    platform_modules = (
        # 1. Lifecycle: health/readiness – nincs platformfüggőség
        get_lifecycle_platform_module(),
        # 2. Settings: PLATFORM_SETTINGS_SERVICE – auth + tenant használja
        get_settings_platform_module(),
        # 3. Users: PLATFORM_USERS_SERVICE – tenant signup használja
        get_users_platform_module(),
        # 4. Auth: PLATFORM_SETTINGS_SERVICE + PLATFORM_CLOCK_SERVICE szükséges
        get_auth_platform_module(),
        # 5. Platform admin: public sémás főadmin auth és user-kezelés
        get_platform_admin_module(),
        # 6. Tenant: PLATFORM_USERS_SERVICE + PLATFORM_CLOCK_SERVICE szükséges
        #    Opcionális: platform usage service – lazy callable, app modul regisztrálja
        get_tenant_platform_module(),
        # 7. Domain: PLATFORM_TENANT_LIFECYCLE_POLICY szükséges (tenant regisztrálja)
        get_domain_platform_module(),
        # 8. Brand: PLATFORM_TENANT_LIFECYCLE_POLICY szükséges (tenant regisztrálja)
        get_brand_platform_module(),
    )
    return build_platform_manifest(
        app_name="Platform API",
        description="Core platform API.",
        version="1.0",
        platform_modules=platform_modules,
    )
