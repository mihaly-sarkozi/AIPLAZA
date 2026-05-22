# core/kernel/db

## Feladat
A `db` könyvtár a kernel közös adatbázis-rétege. Tenant-aware SQLAlchemy session factoryt, ORM base osztályokat, DB instrumentationt, FastAPI session dependencyt és tranzakciós service mixint ad.

## Fájlok
- `model_bases.py`: Közös SQLAlchemy base-ek. A `PublicBase` public sémás platform táblákhoz, a `TenantSchemaBase` tenant sémás táblákhoz, az `AuthBase` kompatibilitási alias.
- `session.py`: Tenant-aware session factory. A `current_tenant_schema` alapján állítja a PostgreSQL `search_path` értékét, kezeli az ambient tranzakciós sessiont és telepíti az engine instrumentationt.
- `session_context.py`: Search path beállítás, SessionProxy és SessionContext helper. A tranzakción belüli commitot flush-ra fordítja.
- `instrumentation.py`: SQLAlchemy engine hookok query timinghoz, DB hiba metrikához és strukturált exception logoláshoz.
- `dependency.py`: FastAPI dependencyként használható DB session provider.
- `transactional_service.py`: Service osztályoknak használható opcionális tranzakciós context mixin.

## Kapcsolódás
A `bootstrap/infrastructure.py` a `make_session_factory()` segítségével hozza létre a runtime DB session factoryt. A repositoryk ezt kapják meg konstruktorban, a modellek pedig a `model_bases.py` base osztályaira épülnek. A tenant kontextust a `core.modules.tenant.context` állítja be, a DB réteg pedig ezt használja a `search_path` beállításához.

## Tenant működés
Ha van aktív tenant schema, a session a tenant sémára állítja a `search_path`-ot. Ha nincs aktív tenant, public sémát használ, így a platform táblák elérhetők maradnak és nem keveredik tenant-adat. Tranzakciós flow-ban ugyanaz a session újrahasznosítható, ezért repository commit helyett flush történik.

## Sárközi Mihály - 2026.05.21
