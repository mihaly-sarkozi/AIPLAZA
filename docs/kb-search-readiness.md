# KB Search readiness contract

A `kb_search` modul **csak** olyan knowledge base-en kereshet, amely production-ready indexing állapotban van.

## Előfeltételek

Mind a következőnek teljesülnie kell:

```text
ready_for_search = true          (kb_processing_metrics.metadata_json)
qdrant_verified = true           (kb_processing_metrics.metadata_json)
indexed_chunks_total > 0
last indexing job status = COMPLETED
last index verification status = COMPLETED
verified_points > 0
missing_points = 0
payload_mismatches = 0
vector_hash_mismatches = 0
```

## Ellenőrzés forrása

1. **Embedding** — `kb_embedding_jobs.status IN (COMPLETED, PARTIAL)` és `chunks_embedded > 0`
2. **Indexing** — `kb_indexing_jobs.status = COMPLETED`, `kb_indexed_chunks.status = INDEXED`
3. **Qdrant verification** — `kb_index_verifications.status = COMPLETED`, chunk szintű `kb_index_verification_items.status = VERIFIED`
4. **Readiness flag** — `MarkReadyForSearchService` állítja be sikeres verification után

## Ha nem teljesül

A `kb_search` modul `SearchNotReadyError`-t dob (tervezett), és **nem** keres a Qdrantban.

## Diagnosztika

Admin endpoint ( `kb.admin` jog):

```text
GET /kb/{knowledge_base_id}/indexing/diagnostics
GET /kb/{knowledge_base_id}/training-items/{training_item_id}/indexing/diagnostics
```

Válasz példa:

```json
{
  "readiness": {
    "ready_for_search": true,
    "qdrant_verified": true,
    "blocking_issues": []
  }
}
```

## Indexing pipeline garancia

Az indexing pipeline a Qdrant upsert után **automatikusan** futtatja a `VerifyQdrantStorageService`-t.
A `kb.indexing_completed` event **csak** teljes verification + readiness siker esetén megy ki.
