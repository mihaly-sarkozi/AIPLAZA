# core/modules/tenant

A `tenant` modul a platform multi-tenant alaprétege. Tenant lifecycle, host/domain alapú feloldás, request tenant context, public és tenant schema kezelés, demo signup, provisioning, tenant cache és extension hookok tartoznak ide.

## Fő felelősség

A modul biztosítja, hogy egy HTTP requestből tenant context legyen, egy új tenant biztonságosan létrejöjjön, a tenant schema táblái települjenek, és az app modulok tenant signup/provisioning hookokon keresztül saját inicializálást köthessenek a folyamatra. Ez platform domain modul: tenant-specifikus üzleti és infrastruktúra-szervező logikát tartalmaz, ezért nem került át a kernel alá.

## Rétegek

- `tenant.py`: `TenantCoreModule`, amely repositorykat, provisioning/sign-up service-eket, routing policyt, routert és tenant hookokat regisztrál.
- `container/`: tenant dependency assembly a repositoryk, schema manager, provisioning és signup use case-ek összekötéséhez.
- `context/`: current tenant schema ContextVar és request tenant context DTO.
- `domain/`: tenant lifecycle és domain routing policy.
- `dto/`: tenant, config, domain, snapshot és status adatcontractok.
- `extensions/`: app modulok által regisztrálható tenant signup/provisioning hook registry.
- `middleware/` és `routing/`: host alapú tenant feloldás, tenant snapshot cache codec, request state és ASGI middleware.
- `models/` és `repositories/`: public schema tenant/config/domain ORM modellek és read/write repository adapterek.
- `schema/`: public schema bootstrap, tenant schema DDL, hook registry, migration és schema orchestration.
- `provisioning/`: új tenant létrehozás validációja, kompenzációs modellje és végrehajtása.
- `signup/`, `slug/`, `tokens/`: demo signup orchestration, abuse control, resend, unsubscribe, slug foglalás és demo login tokenek.
- `service/`: főleg backward-compat importfelület a régi `core.modules.tenant.service.*` útvonalakhoz; canonical kód a fenti csomagokban van.
- `router/`: tenant onboarding és admin tenant HTTP endpointok.

## Kapcsolódás a nagy egészhez

Az `AppManifest` kötelező core platform modulként tölti be a `TenantCoreModule`-t. A modul service kulcsokon publikálja a tenant repositoryt, routing policyt, lifecycle policyt és provisioning/sign-up service-eket; a kernel HTTP pipeline tenant middleware-je és a DB search path kezelés a tenant contextre támaszkodik. A domain kernel és több app modul a tenant DTO-kra, repository portokra, extension hookokra és domain verification szolgáltatásra épít.

## Boundary Döntés

A tenant modul indokoltan marad `core/modules/tenant` alatt. Bár sok infrastruktúrához nyúl, a felelőssége tenant-domain specifikus: tenant azonosítás, tenant lifecycle, provisioning, schema és onboarding. Határeset a `schema/public.py`, mert több platform-wide public táblát is migrál; ezt később külön platform bootstrap/migration egységre lehet bontani, de most a nagy blast radius miatt nem érdemes dokumentációs körben mozgatni.

## Runtime DDL Szabály

Production runtime alatt repository és service kód nem végezhet sémajavítást. Runtime perzisztencia műveletként `SELECT`, `INSERT`, `UPDATE`, `DELETE` engedélyezett; `CREATE TABLE`, `ALTER TABLE`, `ADD COLUMN`, `CREATE INDEX`, `metadata.create_all()` és `ensure column/schema repair` jellegű logika csak migrációs vagy bootstrap lépésben futhat. Public schema DDL helye jelenleg `schema/public.py`, tenant schema DDL helye az app/core `tenant_hooks.py` registry.

## Kompatibilitási Réteg

A `service/`, `service/signup/`, `service/schema/`, valamint néhány `middleware/` és `policies/` fájl backward-compat shim. Ezek régi importútvonalakat tartanak életben, miközben a canonical implementációk a `schema/`, `signup/`, `provisioning/`, `routing/`, `slug/` és `tokens/` csomagokban vannak.

## Kockázatos Fájlok

- `schema/public.py`: public schema bootstrap több platform táblával és indexszel, ezért nagy blast radiusú.
- `middleware/tenant_middleware.py`: request hot path, minden tenant-aware API hívást érint.
- `signup/orchestrator.py`: demo signup, resend, abuse control, token és hook koordináció egy helyen.
- `provisioning/provisioner.py`: tenant schema, public tenant rekord, user, config, domain és kompenzáció összekötése.
- `repositories/demo_signup_repository.py`: raw SQL és demo session/blocklist állapotkezelés.
- `repositories/tenant_write_repository.py`: public tenant mutációk és cache invalidáció együtt.
- `router/tenant_router.py`: HTTP boundary, captcha, rate limit, privacy PDF és hibamapping együtt.

## Sárközi Mihály - 2026.05.21
