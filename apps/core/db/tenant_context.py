# apps/core/db/tenant_context.py
# Tenantonkénti séma: a request search_path-jét ez dönti (middleware beállítja, session factory használja).
# 2026.02.14 - Sárközi Mihály

from contextvars import ContextVar

# Aktuális tenant schema neve (pl. "demo", "acme"). Middleware állítja; session factory ezt használja.
current_tenant_schema: ContextVar[str | None] = ContextVar("current_tenant_schema", default=None)
