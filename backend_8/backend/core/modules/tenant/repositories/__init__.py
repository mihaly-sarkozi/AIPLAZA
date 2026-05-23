# backend/core/modules/tenant/repositories/__init__.py
# Feladat: A tenant repository csomag exportfelülete. Olvasó, író, összefogó tenant repositoryt és demo sign-up repositoryt ad tovább service rétegeknek. Tenant adat-hozzáférési belépési pont.
# Sárközi Mihály - 2026.05.21

def __getattr__(name: str):
    if name == "TenantRepository":
        from core.modules.tenant.repositories.tenant_repository import TenantRepository

        return TenantRepository
    if name == "TenantReadRepository":
        from core.modules.tenant.repositories.tenant_read_repository import TenantReadRepository

        return TenantReadRepository
    if name == "TenantWriteRepository":
        from core.modules.tenant.repositories.tenant_write_repository import TenantWriteRepository

        return TenantWriteRepository
    if name == "DemoSignupRepository":
        from core.modules.tenant.repositories.demo_signup_repository import DemoSignupRepository

        return DemoSignupRepository
    raise AttributeError(name)

__all__ = [
    "TenantRepository",
    "TenantReadRepository",
    "TenantWriteRepository",
    "DemoSignupRepository",
]
