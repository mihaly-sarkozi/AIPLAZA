# Közös SQLAlchemy base-ek a public és tenant sémákhoz.

from sqlalchemy.orm import declarative_base

# Tenant lista: mindig a public sémában (search_path független).
PublicBase = declarative_base()

# Tenantonkénti táblák: minden tenant saját sémában (pl. demo.users, acme.users). search_path dönti el.
TenantSchemaBase = declarative_base()

# Kompatibilitás: a régi AuthBase = TenantSchemaBase
AuthBase = TenantSchemaBase
