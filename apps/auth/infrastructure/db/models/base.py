# apps/auth/infrastructure/db/models/base.py
# PublicBase = csak public.tenants (tenant lista). TenantSchemaBase = tenantonkénti táblák (users, sessions, ...).
# 2026.02.28 - Sárközi Mihály

from sqlalchemy.orm import declarative_base

# Tenant lista: mindig a public sémában (search_path független).
PublicBase = declarative_base()

# Tenantonkénti táblák: minden tenant saját sémában (pl. demo.users, acme.users). search_path dönti el.
TenantSchemaBase = declarative_base()

# Kompatibilitás: a régi AuthBase = TenantSchemaBase
AuthBase = TenantSchemaBase
