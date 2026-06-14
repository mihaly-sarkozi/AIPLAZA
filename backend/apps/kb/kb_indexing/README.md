# kb_indexing

## Felelősség

Embedding vektorok + chunk + discovery bundle alapján **Qdrant payloadot épít**, **upsert**el, majd **production-ready verification** után jelöli a tudástárat kereshetőre.

A keresés (`kb_search`) csak verified + `ready_for_search` állapotra épülhet — lásd `docs/kb-search-readiness.md`.

## Pipeline sorrend

```text
StartIndexingService
  → IndexingPipelineService
    → EnsureQdrantCollectionService
    → BuildQdrantPayloadService / BuildQdrantPointService
    → UpsertQdrantPointsService
    → ValidateIndexingService
    → VerifyQdrantStorageService
    → MarkReadyForSearchService
  → kb.indexing_completed (csak teljes siker esetén)
```

## Input / output event

- `kb.indexing_requested`
- `kb.indexing_completed` — **csak** ha indexing + Qdrant verification sikeres és `ready_for_search=true`

## Táblák

- `kb_indexing_jobs` — indexelési futás
- `kb_indexed_chunks` — chunk ↔ Qdrant point mapping
- `kb_index_verifications` — Qdrant verification futás összesítő
- `kb_index_verification_items` — chunk szintű verification eredmény

## Qdrant verification

`VerifyQdrantStorageService` minden `INDEXED` `kb_indexed_chunks` rekordra:

- collection létezik
- point létezik Qdrantban (retrieve)
- vector + payload jelen van
- payload mezők egyeznek (chunk_id, knowledge_base_id, training_item_id, vector_hash, embedding_id)
- `language_code`, `content_type`, `overall_score` validáció

Hiba esetén processing issue nyílik (`QDRANT_*` kódok).

## Search readiness

`MarkReadyForSearchService` a `kb_processing_metrics.metadata_json` alatt tárolja:

```json
{
  "ready_for_search": true,
  "qdrant_verified": true,
  "search_ready_at": "...",
  "indexed_chunks_total": 120,
  "qdrant_verified_chunks_total": 120
}
```

## Admin diagnosztika

```text
GET /kb/{knowledge_base_id}/indexing/diagnostics          (kb.admin)
GET /kb/{knowledge_base_id}/training-items/{item_id}/indexing/diagnostics
```

## Qdrant adapter

- Lazy client init (`QdrantClientFactory`)
- Config ellenőrzés: `QdrantConfigValidator` — hiányzó URL esetén failed indexing job + `QDRANT_CONFIG_MISSING`
- Payload index típusok: `overall_score → float`, keyword mezők keyword, datetime mezők datetime

## Reindex / delete / rebuild (skeleton)

- `ReindexTrainingItemService`
- `DeleteIndexedChunksService`
- `RebuildKnowledgeBaseIndexService`

## SQL diagnosztika

```sql
SELECT id, status, chunks_total, chunks_indexed, chunks_failed, collection_name, error_code, error_message, created_at, finished_at
FROM kb_indexing_jobs
ORDER BY created_at DESC
LIMIT 20;
```

```sql
SELECT id, chunk_id, embedding_id, qdrant_collection, qdrant_point_id, payload_hash, vector_hash, status, error_code, indexed_at
FROM kb_indexed_chunks
ORDER BY created_at DESC
LIMIT 20;
```

```sql
SELECT id, status, expected_points, verified_points, missing_points, payload_mismatches, vector_hash_mismatches, error_code, error_message, created_at, finished_at
FROM kb_index_verifications
ORDER BY created_at DESC
LIMIT 20;
```

```sql
SELECT id, verification_id, chunk_id, qdrant_point_id, status, error_code, error_message
FROM kb_index_verification_items
ORDER BY created_at DESC
LIMIT 50;
```

## Processing eventek

`QDRANT_VERIFICATION_*`, `READY_FOR_SEARCH_MARKED`, `READY_FOR_SEARCH_BLOCKED`, `INDEXING_DIAGNOSTICS_REQUESTED`

## Issue kódok (kiegészítés)

`QDRANT_POINT_MISSING`, `QDRANT_PAYLOAD_MISMATCH`, `QDRANT_VECTOR_HASH_MISMATCH`, `QDRANT_VERIFICATION_FAILED`, `QDRANT_CONFIG_MISSING`, …
