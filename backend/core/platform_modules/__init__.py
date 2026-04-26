# Ez a fájl a(z) core/platform_modules csomag exportjait és inicializálási pontjait fogja össze.


def get_auth_platform_module():
    from core.platform_modules.auth.module import get_module

    return get_module()


def get_brand_platform_module():
    from core.platform_modules.brand.module import get_module

    return get_module()


def get_domain_platform_module():
    from core.platform_modules.domain.module import get_module

    return get_module()


def get_lifecycle_platform_module():
    from core.platform_modules.lifecycle.module import get_module

    return get_module()


def get_tenant_platform_module():
    from core.platform_modules.tenant.module import get_module

    return get_module()


def get_users_platform_module():
    from core.platform_modules.users.module import get_module

    return get_module()

__all__ = [
    "get_auth_platform_module",
    "get_users_platform_module",
    "get_tenant_platform_module",
    "get_domain_platform_module",
    "get_brand_platform_module",
    "get_lifecycle_platform_module",
]
