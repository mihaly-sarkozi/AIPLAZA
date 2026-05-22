# backend/core/modules/tenant/service/schema_public.py
# Feladat: Kompatibilitási importútvonal a public schema upgrade helperhez. A canonical implementáció a schema/public.py alatt él, ez a fájl régi service importokat tart életben. Backward-compat shim.
# Sárközi Mihály - 2026.05.21

from core.modules.tenant.schema.public import upgrade_public_schema  # noqa: F401

__all__ = ["upgrade_public_schema"]
