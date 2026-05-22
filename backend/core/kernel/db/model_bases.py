# backend/core/kernel/db/model_bases.py
# Feladat: A közös SQLAlchemy declarative base-eket definiálja public és tenant sémás táblákhoz. A PublicBase mindig public sémás platform táblákhoz, a TenantSchemaBase tenantonkénti táblákhoz való, az AuthBase pedig kompatibilitási alias. Core framework szerződés, mert minden ORM modell ezekre épül.
# Sárközi Mihály - 2026.05.21

from sqlalchemy.orm import declarative_base

# Tenant lista: mindig a public sémában (search_path független).
PublicBase = declarative_base()

# Tenantonkénti táblák: minden tenant saját sémában (pl. demo.users, acme.users). search_path dönti el.
TenantSchemaBase = declarative_base()

# Kompatibilitás: a régi AuthBase = TenantSchemaBase
AuthBase = TenantSchemaBase
