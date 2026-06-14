# kb_search

Production-ready Qdrant-alapú keresési modul. **Az AI nem keres** — csak ez a modul hív Qdrantot és Postgres hydrationt.

## Flow

1. `SearchReadinessService` — `ready_for_search`, `qdrant_verified`, index/verification gate
2. `BuildSearchQueryService` — normalizálás, follow-up rewrite (determinisztikus)
3. `BuildQueryEmbeddingService` — runtime query embedding (ugyanaz a modell mint indexelésnél)
4. `QdrantVectorSearchService` + `PayloadFilterService` — kötelező `knowledge_base_id` filter
5. `HybridRankService` — vector + knowledge score
6. `PostgresHydrationService` — chunk text, metadata source of truth
7. `BuildSearchContextService` + `BuildCitationService` — prompt evidence + CIT-n
8. `StoreSearchRunService` — audit táblák (`kb_search_query_*`)

## Chat integráció

`KbSearchChatFacade.build_context_for_chat()` — chat `RetrievalContextBuilder` elsődleges provider-je (`CHAT_USE_KB_SEARCH=true`).

## API

- `POST /api/kb/search` — közvetlen search (kb.read)
  - HTTP hibák: `423` not ready, `503` qdrant failed, `403` permission, `500` unknown
- Download: `get_query_source_download`, `get_query_context_download` a chat routeren keresztül

### Source download endpoint

`GET /api/chat/sources/{query_run_id}/{source_id}/download` jelenleg **citation/evidence export**
(szöveges snippet + metaadatok). Nem szolgálja ki az eredeti betanított dokumentum bináris fájlját.
Eredeti dokumentum letöltéshez később külön endpoint tervezett.

## Env

- `CHAT_USE_KB_SEARCH=true` (default)
- `CHAT_ALLOW_LEGACY_RETRIEVAL=false` (default)
- `KB_SEARCH_TOP_K=10`
- `KB_SEARCH_LANGUAGE_FILTER_MODE=soft` — `off` | `soft` (fallback nyelv filter nélkül) | `strict`

## Source download URL

- **`download_ref`** — belső referencia / source azonosító (pl. `source:chunk_abc123`)
- **`download_url`** — frontend által használható konkrét endpoint (pl. `/api/chat/sources/qry_xxx/chunk_yyy/download`)
- **`download_url_template`** — dokumentált sablon: `/api/chat/sources/{query_run_id}/{source_id}/download`

A pipeline futás közben minden citation/source kap konkrét `download_url`-t, ha ismert a `query_run_id`.

## Search issue logging

Kritikus search hibák a `kb_processing_issues` táblában is megjelennek (`SearchIssueRecorderService`):

| Kód | Severity |
|-----|----------|
| `SEARCH_NO_RESULTS` | INFO |
| `SEARCH_KB_NOT_READY` | WARNING |
| `SEARCH_CONTEXT_EMPTY` | WARNING |
| `SEARCH_QUERY_EMBEDDING_FAILED` | ERROR |
| `SEARCH_QDRANT_FAILED` | ERROR |

Issue metadata tartalmazza: `query_run_id`, `conversation_id`, `question`, `search_status`.

## Channel / audit metadata

`kb_search_query_runs.metadata_json`:

```json
{
  "channel_type": "widget",
  "channel_credential_id": "42",
  "conversation_id": "conv_..."
}
```

## E2E checklist

`qa/chat-search-e2e-checklist.md`
