# KB module

A tudástár backend modulokból áll. Jelenleg telepítve:

1. **kb_crud** — tudástár-kezelés (CRUD + jogosultságok)
2. **kb_ingest** — tanítás (szöveg/fájl beküldés, becslés, batch státusz)

Tervezett (a legacy `apps/knowledge` törlése után újraépítendő) modulok:

- **kb_understanding** — megértés / feldolgozás
- **kb_search** — keresés
- **kb_testing** — tesztelés
- **kb_feedback** — visszajelzés
- **kb_maintenance** — karbantartás / újraindexelés

## Szabályok

- Nincs központi `KnowledgeFacade`.
- Minden modul saját **service** osztályokkal dolgozik (egy felelősség = egy osztály).
- **Egy fájl = egy osztály** (Java-szerű elnevezés: fájlnév = osztálynév, pl. `CreateKnowledgeBaseService.py` → `CreateKnowledgeBaseService`).
- **Ne szaporítsd a kódot:** nincs pass-through wrapper, nincs felesleges `manager` / `handler` / `coordinator` — csak ami döntést vagy perzisztenciát hordoz.
- Audit és metrics modulon belül van, külön service fájlokban (`AuditLogger`, `MetricsRecorder` — ha kell).
- Observability / trace a **kb_understanding** modul része (`LifecycleTracker`, `ProcessingTraceService` — nem külön globális modul).
- A **shared** csak közös típusokat, hibákat, eseményeket tartalmaz — nincs benne üzleti logika.
- **Jogosultság mindig kötelező:** minden route `Depends(require_permission("kb.…"))` — a kulcsok a `bootstrap/app_module.py`-ban deklaráltak.

## Modul belső szerkezet

Minden almodul **külön könyvtárakba** szervezi a felelősségi köröket — ahogy a többi app modulnál (`chat`, `settings`):

```
apps/kb/<modul>/
  README.md
  module.py                 # bootstrap regisztráció (egy osztály)
  router/
    ...Router.py            # HTTP — csak request/response + service hívás
  domain/
    ...                     # modul-specifikus domain (ha kell; különben shared)
  service/
    ...Service.py           # üzleti műveletek, egy osztály / fájl
  repository/               # csak ha van DB/ORM
    ...Repository.py
  adapter/                  # csak ha külső rendszer (storage, queue, vector)
    ...Adapter.py
  schemas/
    ...                     # Pydantic DTO-k (egy request/response / fájl, ha értelmes)
```

**Mi NEM kell minden modulban:** `repository/`, `adapter/`, `domain/` — csak ha tényleg használatban van. Kevesebb fájl > üres váz.

### Példa — `kb_crud/` (váz)

```
kb_crud/
  module.py
  router.py
  use_cases.py
  repository.py
  schemas.py
```

### Példa — `kb_understanding/` (több belső lépés)

```
kb_understanding/
  service/UnderstandMaterialService.py
  service/ChunkTextService.py
  service/VectorizeChunksService.py
  service/IndexChunksService.py
  service/LifecycleTracker.py
  service/ProcessingTraceService.py
  adapter/VectorStoreAdapter.py
```

## Jogosultság

| Szint | Hol |
|-------|-----|
| HTTP | platform `require_permission("kb.read" \| "kb.write" \| "kb.train" \| "kb.admin")` |
| Router | minden route: `Depends(require_permission(...))` |
| Service | tenant / corpus scope ellenőrzés, ha a router nem elég |

**Szabály:** új endpoint = új permission check. Nincs kivétel „dev” vagy „internal” címkével sem production path-on.

## Függés (irány)

```
router.py → modul router → modul service → repository/adapter
                              ↓
                           shared (types, errors, events)

understanding ← reading (esemény / raw ref)
search        ← understanding eredmény (index, chunk)
testing       → search
maintenance   → understanding (esemény)
```

Az almodul könyvtárnevek: `kb_crud`, `kb_reading`, … — önálló egységek, `kb_` prefixszel.

- A **shared** nem importálhat konkrét modult.
- **Service** nem importál más modul **router**ét.
- Modulok között: **shared contracts / events**, ne közvetlen facade.

## Gyökér fa (cél)

```
apps/kb/
  README.md
  router.py
  events.py
  bootstrap/
    app_module.py
  shared/
    types.py
    ids.py
    errors.py
    events.py
    contracts.py
  ports/
  kb_storage/
  kb_crud/
  kb_ingest/
```

## Migráció

Lépésről lépésre, **nem másolunk** a régi `apps/knowledge`-ból — csak a működést vesszük át újraírva.

| Lépés | Tartalom |
|-------|----------|
| 0 | Döntések rögzítése ✓ |
| 1 | Skeleton — mappák, üres osztályok ✓ |
| 2 | shared — types, ids, errors, events, contracts ✓ |
| 3 | modulbekötési szerződés — almodul module.py + app_module ✓ |
| 4 | router.py — almodul routerek összefűzése ✓ |
| 5 | crud — KnowledgeBase CRUD + permission ✓ |
| 6 | training — szöveg/fájl tanítás ✓ |
| 7 | legacy `apps/knowledge` + `apps/knowledge_engine` törlése ✓ |
| 8+ | understanding → search → maintenance → feedback → testing újraépítése |

## Bekötés

A core registry-ben (`apps/registry.py`) a `("kb", "apps.kb.bootstrap.app_module:get_module")` bejegyzés él; a legacy `knowledge` modul törölve. Az `UNDERSTANDING_REQUESTED` outbox eseményt a kb_understanding újraépítéséig egy no-op handler nyugtázza (`apps/kb/events.py`).
