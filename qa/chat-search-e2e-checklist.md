# Chat + KB Search E2E checklist

Manuális ellenőrzési lista a `kb_search + chat` production flow-hoz.

## Előkészítés

1. Legyen egy `READY_FOR_SEARCH` knowledge base (`ready_for_search=true`, `qdrant_verified=true`).
2. Indexelés verification státusza: `COMPLETED`.
3. Qdrant point count > 0.
4. Backend és frontend Dockerben fut.

## Web chat teszt

1. Válassz KB-t a chatben.
2. Tegyél fel releváns kérdést (pl. dokumentumban szereplő kifejezés).
3. Válasz érkezik (`answer_mode=ANSWERED`).
4. `query_run_id` létrejön a válaszban.
5. `sources` megjelennek (forrás gomb / modal).
6. Source modal megnyílik, több citation is listázódik.
7. `context_blocks` látszanak debug módban.
8. Source download működik (`download_url` elsődlegesen).

## No result teszt

1. Kérdezz olyat, ami nincs a KB-ban.
2. `answer_mode = NO_ANSWER`.
3. Nincs hamis source a UI-ban.
4. Turn mentődik `chat_turns`-ba, snapshot üres sources/citations/context_blocks értékkel.

## Not ready teszt

1. Válassz nem ready KB-t (vagy állítsd `ready_for_search=false`).
2. `answer_mode = BLOCKED_NOT_READY`.
3. Nincs LLM hívás.
4. Readiness üzenet megjelenik.
5. Debug/admin módban `diagnostics_url` elérhető.

## Channel teszt

1. Channel ask kérés conversation nélkül.
2. Backend ad session cookie / `conversation_id`-t.
3. Második kérés ugyanazzal a sessionnel — előzmény context működik.
4. `kb_search` lefut `user_id=None` mellett is.
5. `channel_id` formátum: `{channel_type}:{credential_id}` (pl. `widget:42`).
6. Sources visszajönnek.

## Audit SQL

```sql
SELECT id, status, question, channel_id, conversation_id, created_at
FROM kb_search_query_runs
ORDER BY created_at DESC
LIMIT 10;
```

```sql
SELECT id, query_run_id, chunk_id, rank, qdrant_score, hybrid_score
FROM kb_search_query_results
ORDER BY created_at DESC
LIMIT 20;
```

```sql
SELECT id, query_run_id, citation_id, document_title, page_numbers
FROM kb_search_citations
ORDER BY created_at DESC
LIMIT 20;
```

```sql
SELECT id, session_id, role, query_run_id, answer_mode, created_at
FROM chat_turns
ORDER BY created_at DESC
LIMIT 20;
```

```sql
SELECT id, channel_id, metadata_json
FROM chat_sessions
ORDER BY created_at DESC
LIMIT 10;
```

```sql
SELECT issue_code, severity, issue_message, metadata_json
FROM kb_processing_issues
WHERE module = 'kb_search'
ORDER BY created_at DESC
LIMIT 20;
```
