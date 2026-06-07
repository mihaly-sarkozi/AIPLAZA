# kb — tudástár modulcsalád

A teljes `apps/knowledge` modul **7 önálló almodulra** bontása. Nincs központi `KnowledgeFacade`. Minden modul saját routerrel, use case-ekkel, audit/metrics-szel dolgozik.

## Célfa

```
apps/kb/
  README.md                 ← ez a dokumentum
  registry.py               ← 7 modul bekötése a core-ba

  shared/                   ← csak közös típusok, hibák, események, contractok
  api/                      ← router aggregator + jogosultság deps (NEM facade)

  crud/                     ← tudástár-kezelés
  reading/                  ← beolvasás
  understanding/            ← megértés / feldolgozás (+ trace/lifecycle)
  search/                   ← keresés / query context
  testing/                  ← minőség / regresszió
  feedback/                 ← felhasználói visszajelzés
  maintenance/              ← újraindexelés, reprocess, cleanup
```

## A 7 modul (magyarul)

| Modul | Jelentés | Egy mondatban |
|-------|----------|---------------|
| `crud` | tudástár-kezelés | KB létrehozás, jogosultság, forráslista |
| `reading` | beolvasás | text/file/url → valid raw → tárolás → esemény |
| `understanding` | megértés | raw → chunk → embed → index + lifecycle + trace |
| `search` | keresés | kérdés → releváns chunkok / context |
| `testing` | tesztelés | tesztkészlet → search → assertion → riport |
| `feedback` | visszajelzés | jó/rossz találat, rossz forrás, no-answer |
| `maintenance` | karbantartás | reindex, reprocess, withdraw, cleanup |

## Mit NEM csinálunk

- Nem másoljuk 1:1 a régi fájlokat
- Nem építünk új `KnowledgeFacade`-ot
- Nem szedünk szét 15 „támogató” modult (jobs, privacy, observability globálisan)
- PII/GDPR, queue, trace **modulon belül** vagy infrastructure-ben marad, ahol értelmes

---

## Régi → új átviteli térkép

### `crud/` ← tudástár + forrás meta

| Régi hely | Működés (átvenni) |
|-----------|-------------------|
| `router/knowledge_router.py` | `GET/POST/PUT/DELETE /kb`, permissions |
| `service/corpus_management_service.py` | KB CRUD, archiválás |
| `service/corpus_permission_service.py` | jogosultságok |
| `repositories/knowledge_base_repository.py` | KB ORM/repo |
| `models/kb_orm.py`, `kb_user_permission_orm.py` | perzisztencia |
| `api/router.py` (forrás lista) | `GET .../sources`, source content/download |

**Kifelé endpointok:** `/kb`, `/kb/{uuid}`, `/kb/{uuid}/permissions`, `GET /knowledge/corpora/{uuid}/sources`

---

### `reading/` ← ingest / beolvasás

| Régi hely | Működés (átvenni) |
|-----------|-------------------|
| `api/router.py` | text/file/url ingest, run lista, run status |
| `api/file_ingest_use_cases.py` | fájl ingest flow |
| `api/upload_support.py` | quota, MFA, malware scan, limit |
| `application/` (ingest app service) | run létrehozás + queue |
| `service/ingest_run_creation_service.py` | run/input létrehozás |
| `service/url_fetch_service.py`, `url_ingest_security.py` | URL ingest |
| `service/source_storage_service.py` | raw tárolás |
| `ingest_jobs.py`, `api/background_jobs.py` | queue publish |
| `repositories/knowledge_ingest_repository.py` | ingest ORM |

**Kifelé endpointok:**

- `POST /knowledge/corpora/{uuid}/ingest/text`
- `POST .../ingest/files`, `.../estimate`
- `POST .../ingest/urls`
- `GET .../ingest/runs`, `GET /knowledge/ingest/runs/{run_id}`
- `GET .../ingest/items/{id}/raw`

**Nem ide:** chunking, embedding, index, keresés

**Esemény kifelé:** `UnderstandingRequestedEvent` (shared)

---

### `understanding/` ← feldolgozás + életciklus + trace

| Régi hely | Működés (átvenni — első körben egyszerűsítve) |
|-----------|-----------------------------------------------|
| `service/parser_orchestrator.py` | raw → text |
| `service/chunking_service.py` | darabolás |
| `ai/embedding_provider.py`, `ai/embedding_service.py` | embedding |
| `qdrant/`, index build | vector index |
| `service/index_build_service.py` | index build run |
| `service/ingest_run_processor.py` | háttér feldolgozás |
| `service/ingest_pipeline_progress_service.py` | progress |
| `service/knowledge_trace_service.py` | trace |
| `service/knowledge_trace_query_service.py` | trace lekérdezés |
| `service/knowledge_trace_payload_builder.py` | trace payload |
| `api/background_jobs.py` | worker belépés |

**Későbbi kör (NE az első migrációban):**

- claim extraction, semantic blocks, entity clusters
- `document_interpretation_service.py`, `sentence_interpretation_*`
- `pii_gdpr/` teljes pipeline → understanding belső alfunkcióként, ha kell

**Kifelé endpointok:**

- `GET /knowledge/dev/ingest-runs/{run_id}/trace` (compat)
- `GET /knowledge/index-builds/{build_id}` (státusz — vagy maintenance)
- `GET .../sentences`, `.../paragraphs` (később / compat)

**Lifecycle státuszok:** `received → processing → chunked → vectorized → indexed → completed | failed`

**Trace:** `understanding/trace.py` — nem külön observability modul

---

### `search/` ← retrieval / query context

| Régi hely | Működés (átvenni) |
|-----------|-------------------|
| `service/retrieval_service.py` | fő retrieval |
| `service/query_aware_retrieval_v0.py` | query-aware search |
| `service/query_resolver_v0.py` | query feloldás |
| `service/explanation_builder_v0.py` | magyarázat meta |
| `service/lineage_builder_v0.py` | forrás lineage (opcionális compat) |
| `service/search_profile_builder_v1.py` | profile |
| `domain/retrieval_profile.py`, `context_profile.py` | profile domain |

**Kifelé endpointok:**

- `POST /knowledge/retrieve`
- `POST /knowledge/chat-context`

**Nem ide:** ingest, feldolgozás, feedback mentés logikája

---

### `testing/` ← minőség / regresszió

| Régi hely | Működés (átvenni — egyszerűsítve) |
|-----------|-----------------------------------|
| `service/knowledge_quality_report_v0.py` | quality report |
| `service/knowledge_report_service.py` | riport |
| `api/router.py` | `GET .../quality-report` (compat → testing) |

**Új, tisztább:** tesztkészlet, assertion, regressziós futás

**Használja:** `search` modult (tiltott: search → testing)

**Kifelé (új + compat):**

- `GET /knowledge/corpora/{uuid}/quality-report`
- `POST /knowledge/tests`, `POST .../tests/{id}/run` (új)

---

### `feedback/` ← felhasználói visszajelzés

| Régi hely | Működés (átvenni) |
|-----------|-------------------|
| `service/knowledge_feedback_service.py` | feedback mentés, claim correction |
| `api/router.py` | `POST .../feedback` |

**Kifelé:** `POST /knowledge/corpora/{uuid}/feedback`

**Nem ugyanaz mint testing:** feedback = user input, testing = dev/QA

---

### `maintenance/` ← karbantartás

| Régi hely | Működés (átvenni) |
|-----------|-------------------|
| `service/ingest_reprocess_service.py` | run reprocess |
| `service/ingest_item_reprocess_service.py` | item reprocess |
| `service/semantic_index_refresh_service.py` | index refresh |
| `service/ingest_auto_index_service.py` | auto index |
| `service/parse_output_cleanup_service.py` | cleanup |
| `service/ingest_item_cleanup_service.py` | item cleanup |
| `api/router.py` | reprocess, withdraw, index-build start |

**Kifelé endpointok:**

- `POST /knowledge/ingest/items/{id}/reprocess`
- `POST /knowledge/index-builds`
- `POST .../sources/{id}/withdraw`
- `PATCH .../semantic-blocks/{id}/status` (később / compat)

**Használja:** `understanding` flow-t (eseményen keresztül, ne közvetlen facade)

---

### `shared/` ← csak közös

| Régi hely | Mit viszünk át |
|-----------|----------------|
| `errors.py` | `KnowledgeError`, `NotFound`, `Validation`, `Permission`, `Processing` |
| `domain/corpus.py`, `domain/kb.py` | minimális shared típusok |
| `events.py` | cross-modul esemény nevek |
| — | `contracts.py`: `ReadMaterialRef`, `SearchContextItem` |

**Ne kerüljön ide:** service logika, ORM, router

---

### `api/` ← aggregator + jogosultság

| Régi hely | Mit viszünk át |
|-----------|----------------|
| `bootstrap/dependencies.py` | → `api/deps.py` (require_read/write/admin/train) |
| `api/router.py` | → csak `include_router` hívások, NEM üzleti logika |

---

### Ki kell vezetni (ne migráljuk)

| Régi | Miért |
|------|-------|
| `service/knowledge_service.py` + összes `facade_*` | helyette 7 modul use case |
| `service/facade_runtime.py`, `facade_wiring_*` | wiring → `registry.py` + modul `module.py` |
| `container/knowledge_container.py` | helyette modulonkénti DI |
| Claim/semantic/entity teljes stack | csak ha tényleg kell — későbbi understanding alfunkció |

---

## Infrastructure (modulok alatt, nem shared üzleti logika)

A régi `infrastructure.py`, `qdrant/`, `ai/` technikai részei modulonként injektálhatók, vagy később:

```
apps/kb/shared/infrastructure/   ← csak ha tényleg közös
  db.py
  object_storage.py
  vector_store.py
  embeddings.py
  queue.py
```

Első körben elég stub/in-memory; MySQL/Qdrant bekötés modulonként, ahogy készül.

---

## Bekötés (új modell)

```
apps/registry.py
  → apps/kb/registry.py
      → KbCrudModule
      → KbReadingModule
      → KbUnderstandingModule
      → KbSearchModule
      → KbTestingModule
      → KbFeedbackModule
      → KbMaintenanceModule
```

Minden `module.py`:

```python
class KbReadingModule:
    def register_services(self, container): ...
    def register_routes(self, app): ...      # vagy RouteRegistration tuple
    def register_event_handlers(self, bus): ...
```

**Core app:** egy `kb` app modul regisztráció (`apps/kb/bootstrap/app_module.py`), ami a `KB_MODULES`-t tölti.

**API prefix:** `/api` — compat endpointok változatlanok maradnak.

**Átmenet:** `DISABLED_APP_MODULES=knowledge` csak amikor az új modulok átvették az összes endpointot.

---

## Függési szabály

```
crud          → shared
reading       → shared, crud (csak ID / permission check API-n)
understanding → shared, reading output (raw ref)
search        → shared, understanding output (index/chunks)
testing       → shared, search
feedback      → shared (+ search run ref)
maintenance   → shared, understanding (esemény)

TILTOTT:
  search → reading
  search → understanding (közvetlen use case)
  reading → search
  crud → reading (use case szinten)
  feedback → maintenance
  shared → bármelyik modul
```

---

## Migrációs lépések (kicsi, vizsgálható)

Minden lépés: **skeleton → 1 működő flow → compat router átáll → régi kód törlése csak utána**.

### 0. lépés — modulfa skeleton (1 PR)

- `apps/kb/` mappa + minden almodul: `README`, `module.py`, `router.py`, `use_cases.py`, `audit.py`, `metrics.py`
- `shared/`, `api/router.py`, `api/deps.py`, `registry.py`
- Import boundary teszt
- **Nincs** legacy törlés, **nincs** facade

### 1. lépés — `shared` + `api/deps`

- közös errors, types, events, contracts
- jogosultság deps (read/write/train/admin)

### 2. lépés — `crud` (ELSŐ MŰKÖDŐ)

- KB list/create/update/delete
- permissions
- forrás lista (read-only meta)
- compat: `/kb/*`
- **Miért először:** minden más modulnak kell `corpus_uuid`

### 3. lépés — `reading` (text only)

- text ingest + validálás + raw storage + ReadRun
- `UnderstandingRequested` event
- compat: `POST .../ingest/text`, `GET .../runs/{id}`
- MFA/quota: reading belső vagy deps

### 4. lépés — `understanding` (minimális gerinc)

- text raw → chunk → embed → Qdrant
- `lifecycle.py` + `trace.py`
- worker / queue handler
- compat: trace endpoint
- **Ez a kritikus path** — csak utána search

### 5. lépés — `search`

- retrieve + chat-context
- compat: `/knowledge/retrieve`, `/knowledge/chat-context`

### 6. lépés — `reading` (file)

- file ingest, estimate, upload policy

### 7. lépés — `testing`

- smoke tesztkészlet + quality report compat

### 8. lépés — `feedback`

- POST feedback compat

### 9. lépés — `maintenance`

- reprocess, index-build, withdraw, cleanup

### 10. lépés — legacy kivezetés

- `apps/knowledge` kikapcsolása
- chat modul függőség átállítása (`KNOWLEDGE_SERVICE` → kb search/reading contract)
- facade törlés

---

## Modulonkénti „kész” checklist

Minden modulnál:

- [ ] `README.md` — felelősség + tiltott importok
- [ ] `use_cases.py` — stub nélkül legalább 1 happy path
- [ ] `router.py` — compat endpointok bekötve
- [ ] `audit.py` — CRUD/ingest/search esemény napló
- [ ] `metrics.py` — modul-specifikus számlálók
- [ ] unit teszt a use case-re
- [ ] import boundary teszt
- [ ] compat API teszt (régi path, régi response shape)

---

## Endpoint → modul gyors referencia

| Endpoint | Modul |
|----------|-------|
| `/kb` | crud |
| `/knowledge/corpora/{uuid}/ingest/*` | reading |
| `/knowledge/ingest/runs/*` | reading |
| `/knowledge/dev/ingest-runs/*/trace` | understanding |
| `/knowledge/ingest/items/*/reprocess` | maintenance |
| `/knowledge/index-builds` | maintenance (+ understanding worker) |
| `/knowledge/retrieve` | search |
| `/knowledge/chat-context` | search |
| `/knowledge/corpora/{uuid}/feedback` | feedback |
| `/knowledge/corpora/{uuid}/quality-report` | testing |
| `/knowledge/metrics` | **modulonként aggregálva** (search/reading/crud saját metrics → api összesítés később) |
| `/knowledge/corpora/{uuid}/sources/*/withdraw` | maintenance |

---

## Következő konkrét teendő

**0. lépés skeleton PR** — csak mappák, README-k, üres use case stubok, `registry.py`, import szabályok. Semmi legacy áthelyezés.

Utána **2. lépés: crud** — első valódi működő modul.
