# KB modul — tudástár architektúra

A tudástár nem egy nagy modul, hanem egymásra épülő, külön fejleszthető és külön
tesztelhető komponensek rendszere. A „Training" üzleti fogalom marad, de technikailag
több modulból áll:

```text
Training = Ingest + Understanding + Indexing + Validation
```

## Végleges modulnévsor

| Modul | Állapot | Feladat |
|-------|---------|---------|
| **kb_crud** | telepítve | tudástár CRUD, jogosultságok, tenant kezelés, státuszok, alapbeállítások |
| **kb_ingest** | telepítve | input befogadás + bizonyíték mentés (szöveg/PDF/DOCX, checksum, batch/item, feldolgozás indítása) |
| **kb_understanding** | telepítve | technikai előkészítés: extract → normalize → chunk → validate |
| **kb_discovery** | telepítve | lokális felismerés: person, entity, keyword, topic, time, space, relationship, scoring |
| **kb_indexing** | skeleton | a feldolgozott tudás kereshetővé tétele (full-text, vector, entity, keyword, metadata, hybrid index) |
| **kb_search** | skeleton | keresés és kontextusépítés (query parser, hybrid ranking, context/citation builder) |
| **kb_services** | skeleton | tudásra épülő üzleti szolgáltatások (vázlat, összefoglaló, Q&A, hiánylista, tudástérkép…) |
| **kb_testing** | skeleton | a teljes tudásfolyamat minőségének mérése (pipeline-lépésenkénti tesztek) |
| **kb_feedback** | skeleton | felhasználói visszajelzések és használati jelek gyűjtése |
| **kb_maintenance** | skeleton | hosszú távú karbantartás (újraindexelés, újraembedding, retry, cleanup) |

A `kb_training` és `kb_reading` technikai modulnevek megszűntek — helyettük: **kb_ingest**.

## Modulhatárok (mit NEM csinál)

- **kb_crud** nem végez betöltést, feldolgozást, embeddinget vagy keresést.
- **kb_ingest** nem értelmez, nem chunkol, nem embeddingel. Célja: bizonyíték biztonságos
  eltárolása + a feldolgozási folyamat elindítása.
- **kb_understanding** nem ír keresőindexet és nem szolgál ki keresést.
- **kb_indexing** külön modul, mert **írja** az indexeket; a **kb_search** külön modul,
  mert **olvassa** őket.
- **kb_search** nem dolgoz fel dokumentumot és nem módosítja a tudásanyagot.
- **kb_services** a `kb_search`, `kb_understanding`, `kb_feedback` és `kb_indexing`
  eredményeire épülhet, de nem végezhet nyers dokumentumfeldolgozást. Alapja:
  chunks, entities, relationships, summaries, keywords, topics, scores,
  search_events, feedback.

## Pipeline szabály

```text
INGEST → EXTRACT → NORMALIZE → CHUNKING → VALIDATION
→ DISCOVERY (person, entity, temporal, spatial, keyword, topic, …)
→ EMBEDDING → INDEXING → SEARCH
```

Ezt **tilos** egyetlen nagy függvényként vagy service-ként megvalósítani. Minden lépés
külön egység: külön class, külön service, külön input/output DTO, külön log, külön teszt.
Az `UnderstandingPipelineService` csak összefűzi a lépéseket — nem abban van a logika.

Minden lépésnek legyen: saját bemenete, kimenete, státusza, hibakezelése, tesztje és
naplózható eredménye. Egy lépés hibája nem teheti tönkre az egész tudástárat — az adott
item legyen `FAILED`, `PARTIAL` vagy `RETRYABLE` állapotú.

## Állapotkezelési szabály

Minden dokumentum, batch és item kapjon státuszt. A kanonikus státuszkészlet
(`kb_understanding/enums/UnderstandingStatus.py`):

```text
CREATED, QUEUED, EXTRACTING, NORMALIZING, CHUNKING,
VALIDATING, READY_FOR_DISCOVERY, PARTIAL, FAILED, RETRYABLE
```

A discovery / embedding / scoring státuszok a `kb_discovery` modulban vannak.

## Bizonyíték szabály

Minden tudáselemnek visszavezethetőnek kell lennie az eredeti forrásra. Kötelező
metaadatok minden chunkon/tudáselemen:

```text
source_id, document_id, chunk_id, file_name, source_type, checksum, version,
page_number vagy section, created_by, created_at, last_processed_at
```

Az AI-válasz nem lehet „bizonyíték nélküli".

## Tesztelhetőségi szabály

Minden pipeline-lépésnél ellenőrizhető legyen: mit kapott bemenetként, mit adott
kimenetként, mennyi ideig futott, hibázott-e, újrafuttatható-e, módosított-e adatot.
A feldolgozás legyen **idempotens**: ugyanarra az inputra ugyanazt vagy kompatibilis
eredményt adja. Minden összetett pipeline-lépéshez tartozzon külön teszt
(ingest, extract, normalize, chunking, entity extraction, embedding, indexing,
search, ranking, AI válasz, forrásellenőrzés).

## Bővíthetőségi szabály

Új inputforrás vagy embedder hozzáadásakor nem szabad módosítani az egész pipeline-t —
új forrás/szolgáltató csak új **adapter** legyen:

```text
PdfIngestAdapter, DocxIngestAdapter, ManualTextIngestAdapter, UrlIngestAdapter
OpenAIEmbedder, LocalEmbedder, HuggingFaceEmbedder, CustomEmbedder
```

## Könyvtárszabály

Minden almodul helye: `backend/apps/kb/<modul_neve>/`. A **kb_ingest a minta**.

Kötelező minden modulban:

| Elem | Szerep |
|------|--------|
| `module.py` | bekötés: route-ok, service-ek/repository-k, event handler-ek regisztrálása |
| `bootstrap/` | `dependencies.py` (FastAPI Depends), `service_keys.py` (container kulcsok), `tenant_hooks.py` (ha van tenant DB tábla) |
| `service/` | üzleti logika — egy felelősség = egy service osztály, egy fájl = egy osztály |
| `dto/` | request/response/command/result DTO-k |
| `errors/` | modulspecifikus hibák |

Opcionális, csak ha tényleg kell (**kevesebb fájl > üres váz**):

| Elem | Mikor kell |
|------|-----------|
| `router/` | ha van HTTP API — csak request/response + service hívás, nincs üzleti logika, minden endpointon permission check |
| `orm/` | ha a modul saját táblákat kezel |
| `repository/` | ha a modul DB-ből ír/olvas |
| `adapters/` | külső vagy technikai integrációk |
| `validation/` | input vagy pipeline-lépés validáció |
| `enums/` | státuszok, típusok, hibakódok |
| `mapper/` | DTO ↔ domain ↔ ORM átalakítás |
| `events/` | ha a modul eseményeket bocsát ki vagy fogad |
| `security/` | modulspecifikus biztonsági ellenőrzések (pl. `FileSniffer`, `ArchiveGuard`) |

További szabályok:

- Nincs központi `KnowledgeFacade`.
- **Egy fájl = egy osztály** (fájlnév = osztálynév, pl. `ChunkContentService.py`).
- **Ne szaporítsd a kódot:** nincs pass-through wrapper, nincs felesleges
  `manager` / `handler` / `coordinator` — csak ami döntést vagy perzisztenciát hordoz.
- Audit és metrics modulon belül van, külön service fájlokban.
- Observability / trace a **kb_processing** része (`kb_processing_events`, `ProcessingEventService`).
- A **shared** csak közös típusokat, hibákat, eseményeket tartalmaz — nincs benne
  üzleti logika, és nem importálhat konkrét modult.

## Bekötési szabály

Új modul hozzáadásakor pontosan 4 helyen kell nyúlni:

1. Új mappa: `backend/apps/kb/<modul_neve>/`
2. Saját `module.py` (`name`, `register_routes`, `register_services`, `register_event_handlers`)
3. `backend/apps/kb/bootstrap/app_module.py` — a `KB_MODULES` listába bekerül a modul példánya
4. `backend/apps/kb/router.py` — csak ha van HTTP routere

## Jogosultság

| Szint | Hol |
|-------|-----|
| HTTP | platform `require_permission("kb.read" \| "kb.write" \| "kb.train" \| "kb.admin")` |
| Router | minden route: `Depends(require_permission(...))` |
| Service | tenant / corpus scope ellenőrzés, ha a router nem elég |

**Szabály:** új endpoint = új permission check. Nincs kivétel „dev" vagy „internal"
címkével sem production path-on.

## Függés (irány)

```text
router.py → modul router → modul service → repository/adapter
                              ↓
                           shared (types, errors, events)

understanding ← ingest (esemény / raw ref)
indexing      ← understanding (esemény / chunk + embedding)
search        ← indexing eredmény (indexek olvasása)
services      ← search / understanding / feedback / indexing eredmények
testing       → search
feedback      → ranking / hiánylista / statisztika / karbantartás bemenete
maintenance   → understanding (esemény / újrafuttatás)
```

- A **shared** nem importálhat konkrét modult.
- **Service** nem importál más modul **router**ét.
- **Modulok között tilos a közvetlen kereszt-import** (`apps.kb.kb_X` nem importál
  `apps.kb.kb_Y`-t) — kommunikáció: **shared contracts / events** + container-ben
  regisztrált portok. Kompozíciós gyökér kivétel: `apps/kb/router.py`,
  `apps/kb/bootstrap/`, `apps/kb/events.py`.
- A szabályokat a `scripts/check_import_boundaries.py` gépileg is kikényszeríti.

## Fejlesztési sorrend

```text
 1. kb_crud                                ✓
 2. kb_ingest                              ✓
 3. kb_understanding / extract
 4. kb_understanding / normalize
 5. kb_understanding / chunking
 6. kb_understanding / validation
 7. kb_discovery / entity + enrichment + scoring
 8. kb_embedding / vector
 9. kb_indexing / full-text + vector index
10. kb_search / hybrid search
11. kb_services / question-answer
12. kb_feedback
13. kb_testing
14. kb_maintenance
```

## Gyökér fa

```text
apps/kb/
  README.md
  router.py
  events.py
  module.py
  bootstrap/
    app_module.py
    service_keys.py
  shared/
    types.py
    ids.py
    errors.py
    events.py
    contracts.py
  ports/
  kb_crud/
  kb_ingest/
  kb_understanding/
  kb_indexing/
  kb_search/
  kb_services/
  kb_testing/
  kb_feedback/
  kb_maintenance/
```

## Bekötés a platformba

A core registry-ben (`apps/registry.py`) a
`("kb", "apps.kb.bootstrap.app_module:get_module")` bejegyzés él. Az
`UNDERSTANDING_REQUESTED` outbox eseményt a kb_understanding tényleges
megvalósításáig egy no-op handler nyugtázza (`apps/kb/events.py`).
