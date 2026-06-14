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
- Download: `get_query_source_download`, `get_query_context_download` a chat routeren keresztül

## Env

- `CHAT_USE_KB_SEARCH=true` (default)
- `CHAT_ALLOW_LEGACY_RETRIEVAL=false` (default)
- `KB_SEARCH_TOP_K=10`
- `KB_SEARCH_LANGUAGE_FILTER_MODE=soft` — `off` | `soft` (fallback nyelv filter nélkül) | `strict`

## Source download URL

Kanokikus template: `/api/chat/sources/{query_run_id}/{source_id}/download`

A pipeline futás közben konkrét URL kerül a `download_ref` / `download_url` mezőbe; a `download_url_template` mező mindig dokumentálja a sablont.
