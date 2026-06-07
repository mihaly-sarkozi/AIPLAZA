from __future__ import annotations

# backend/shared/utils/tenant_slug.py
# Feladat: Bérlő slug normalizálása és alapértelmezett érték.
# Sárközi Mihály - 2026.06.07


def tenant_slug_or_default(tenant: object | str | None, *, default: str = "default") -> str:
    """Visszaadja a bérlő slug-ját, vagy az alapértelmezett értéket."""
    if isinstance(tenant, str):
        raw = tenant
    else:
        raw = getattr(tenant, "slug", None)
    slug = str(raw or "").strip()
    return slug or default


__all__ = ["tenant_slug_or_default"]
