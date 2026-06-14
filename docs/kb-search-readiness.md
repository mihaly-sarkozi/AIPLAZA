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
3. **Qdrant verification** — `kb_index_verifications.status = COMPLETED`
4. **Readiness flag** — `MarkReadyForSearchService` sikeres verification után

## Reindex / rebuild és readiness

- **Reindex training item** — régi Qdrant pointok törlése/replace, új indexing + verification, majd `ready_for_search` újraértékelés
- **Rebuild KB index** — teljes KB Qdrant törlés + itemenkénti reindex; `kb_index_rebuilds` audit; `search_status` a metrics-ben
- Rebuild/reindex partial esetén: `ready_for_search = false`, `search_status = SEARCH_PARTIAL` vagy `SEARCH_NOT_READY`
- **`READY_FOR_SEARCH` csak akkor igaz**, ha rebuild/indexing `COMPLETED`, `points_reindexed > 0`, **`points_verified = points_reindexed`**, és nincs blocking issue
- Partial rebuild után (`points_verified < points_reindexed`) a keresés nem engedélyezett

## Ha nem teljesül

A `kb_search` modul `SearchNotReadyError`-t dob — implementálva: `SearchReadinessService`.

Chat response: `answer_mode=BLOCKED_NOT_READY`, egységes readiness payload:

```json
{
  "answer_mode": "BLOCKED_NOT_READY",
  "readiness": {
    "ready_for_search": false,
    "qdrant_verified": false,
    "blocking_issues": ["..."]
  },
  "sources": [],
  "citations": [],
  "context_blocks": []
}
```

Debug/admin módban: `debug.diagnostics_url = /api/kb/{knowledge_base_id}/indexing/diagnostics`

## Search hibák monitoring

Fontos search események a `kb_processing_issues` táblában is (`module=kb_search`). Lásd `backend/apps/kb/kb_search/README.md`.

## E2E checklist

`qa/chat-search-e2e-checklist.md`

## Diagnosztika

```text
GET /kb/{knowledge_base_id}/indexing/diagnostics
GET /kb/{knowledge_base_id}/training-items/{training_item_id}/indexing/diagnostics
```

## Indexing pipeline garancia

Qdrant upsert után automatikus `VerifyQdrantStorageService`.
`kb.indexing_completed` csak teljes verification + readiness siker esetén.

## Failed indexing visibility

Minden `kb.indexing_requested` hiba (embedding hiány, KB not found, Qdrant config) → failed `kb_indexing_jobs` + processing issue. A monitoring nem marad üresen job nélkül.

## Event wiring

KB event handlerek canonical helye: `backend/apps/kb/events.py`.
