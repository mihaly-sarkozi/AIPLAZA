# kb_indexing

## Felelősség

Embedding vektorok + chunk + discovery bundle alapján **Qdrant payloadot épít**, **upsert**el, majd **production-ready verification** után jelöli a tudástárat kereshetőre.

A keresés (`kb_search`) csak verified + `ready_for_search` állapotra épülhet — lásd [`docs/kb-search-readiness.md`](../../../../docs/kb-search-readiness.md).

## Event wiring

**Canonical hely:** [`apps/kb/events.py`](../events.py) — minden KB cross-module event handler (understanding → discovery → embedding → indexing) itt regisztrálódik.

A `KbIndexingModule.register_event_handlers()` szándékos no-op; ne duplikálj handler regisztrációt modul szinten.

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

## Failed job láthatóság

`StartIndexingService` + `IndexingFailureRecorderService`: minden ismert előfeltétel-hiba **failed `kb_indexing_jobs` rekordot** hoz létre + processing event/issue-t:

- `EMBEDDING_JOB_NOT_FOUND`
- `EMBEDDING_NOT_READY`
- `QDRANT_COLLECTION_MISSING` / `QDRANT_CONFIG_MISSING`
- `KNOWLEDGE_BASE_NOT_FOUND`
- `NO_EMBEDDINGS_FOR_INDEXING`

Eventek: `INDEXING_REQUEST_RECEIVED`, `INDEXING_FAILED_BEFORE_JOB_START`, `INDEXING_FAILED`, `INDEXING_JOB_CREATED`.

## Reindex training item

`ReindexTrainingItemService.reindex()`:

```text
régi Qdrant pointok törlése (DeleteIndexedChunksService)
kb_indexed_chunks → REPLACED
új indexing job (StartIndexingService → pipeline → verify → ready)
```

Eventek: `REINDEX_*`. Issue-k: `REINDEX_*`.

Idempotencia: aktív indexing job training itemre → `JOB_ALREADY_RUNNING` (kivéve `force=true`).

## Delete indexed chunks

`DeleteIndexedChunksService` — Qdrant delete + Postgres soft-state:

- `training_item_id` / `chunk_id` lista / `indexing_job_id` / teljes `knowledge_base_id`
- státuszok: `INDEXED`, `REMOVED`, `REPLACED`, `DELETE_FAILED`
- metadata: `removed_at`, `removed_by`, `remove_reason`

## Rebuild knowledge base index

`RebuildKnowledgeBaseIndexService.rebuild()` — Postgres source of truth, Qdrant újraépítés:

```text
POINT_DELETE_AND_REINDEX (default)
  → összes INDEXED chunk törlése Qdrantból
  → training itemenként ReindexTrainingItemService
  → kb_index_rebuilds audit rekord
```

`RECREATE_COLLECTION` → explicit `UNSUPPORTED_REBUILD_MODE` (nincs néma NotImplemented).

### Rebuild audit mezők (`kb_index_rebuilds`)

| Mező | Jelentés |
|------|----------|
| `points_deleted` | Régi Qdrant pointok törlése / `REPLACED` státusz (KB-wide delete + item szintű törlés maximuma) |
| `points_reindexed` | Újonnan Qdrantba upsertelt pointok száma (`chunks_indexed` összesítve) |
| `points_verified` | Qdrant verification által visszaigazolt új pointok száma |

A három mező **külön jelentésű** — nem szabad összekeverni (pl. `points_reindexed += points_deleted` hibás).

Rebuild státusz:

- `COMPLETED` — minden item sikeres, `points_verified = points_reindexed > 0`
- `PARTIAL` — van sikeres reindex, de item hiba vagy `points_verified < points_reindexed`
- `FAILED` — `points_reindexed = 0` vagy minden item failed

Metrics metadata: `search_status`, `last_rebuild_job_id`, `rebuild_finished_at`, `ready_for_search`.

## Táblák

- `kb_indexing_jobs`
- `kb_indexed_chunks`
- `kb_index_verifications`
- `kb_index_verification_items`
- `kb_index_rebuilds`

Tenant séma: `kb.indexing.schema.v3`

## Qdrant verification

`VerifyQdrantStorageService` minden `INDEXED` chunkra retrieve + payload/vector ellenőrzés.

## Search readiness

`MarkReadyForSearchService` → `kb_processing_metrics.metadata_json`:

```json
{
  "ready_for_search": true,
  "qdrant_verified": true,
  "indexed_chunks_total": 120
}
```

Csak sikeres verification után.

## Admin diagnosztika

```text
GET /kb/{knowledge_base_id}/indexing/diagnostics          (kb.admin)
GET /kb/{knowledge_base_id}/training-items/{item_id}/indexing/diagnostics
```

## SQL diagnosztika

```sql
SELECT id, status, error_code, error_message, created_at, finished_at
FROM kb_indexing_jobs
ORDER BY created_at DESC
LIMIT 20;
```

```sql
SELECT id, chunk_id, qdrant_point_id, status, error_code, metadata_json
FROM kb_indexed_chunks
ORDER BY created_at DESC
LIMIT 20;
```

```sql
SELECT id, status, expected_points, verified_points, missing_points,
       payload_mismatches, vector_hash_mismatches
FROM kb_index_verifications
ORDER BY created_at DESC
LIMIT 20;
```

```sql
SELECT id, status, mode, training_items_total, training_items_reindexed,
       training_items_failed, points_deleted, points_reindexed, points_verified
FROM kb_index_rebuilds
ORDER BY created_at DESC
LIMIT 20;
```
