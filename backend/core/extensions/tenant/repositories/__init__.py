# Ez a fájl a(z) core/extensions/tenant/repositories csomag exportjait és inicializálási pontjait fogja össze.


def __getattr__(name: str):
    if name == "TenantRepository":
        from core.extensions.tenant.repositories.tenant_repository import TenantRepository

        return TenantRepository
    if name == "TenantReadRepository":
        from core.extensions.tenant.repositories.tenant_read_repository import TenantReadRepository

        return TenantReadRepository
    if name == "TenantWriteRepository":
        from core.extensions.tenant.repositories.tenant_write_repository import TenantWriteRepository

        return TenantWriteRepository
    if name == "DemoSignupRepository":
        from core.extensions.tenant.repositories.demo_signup_repository import DemoSignupRepository

        return DemoSignupRepository
    raise AttributeError(name)

__all__ = [
    "TenantRepository",
    "TenantReadRepository",
    "TenantWriteRepository",
    "DemoSignupRepository",
]
