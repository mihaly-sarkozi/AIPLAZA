# kb_search

Keresés és kontextusépítés a `kb_indexing` által írt indexek fölött.

**Szabály:** a `kb_search` nem dolgoz fel dokumentumot és nem módosítja a
tudásanyagot — csak olvassa az indexeket. Minden találat visszavezethető a
forrásra (citation builder, bizonyíték szabály).

**Readiness contract:** a keresés csak verified + `ready_for_search` KB-n fut.
Részletek: [`docs/kb-search-readiness.md`](../../../../docs/kb-search-readiness.md).

## Részei

```text
query parser, full-text search, vector search, entity search,
metadata filter, hybrid ranking, context builder, citation builder
```

## Cél-szerkezet

```text
kb_search/
├── module.py                        ✓ (skeleton)
├── bootstrap/
│   ├── dependencies.py
│   └── service_keys.py              ✓ (skeleton)
├── router/
│   └── SearchRouter.py
├── dto/
├── enums/
├── service/
│   ├── ParseQueryService.py
│   ├── FullTextSearchService.py
│   ├── VectorSearchService.py
│   ├── EntitySearchService.py
│   ├── HybridSearchService.py
│   ├── RankResultsService.py
│   ├── BuildContextService.py
│   └── BuildCitationService.py
├── repository/
│   └── SearchRepository.py
├── mapper/
│   └── search_result_mapper.py
└── validation/
    └── ValidateSearchQuery.py
```

## Fejlesztési sorrend (a teljes KB sorrendből)

hybrid search (10.)
