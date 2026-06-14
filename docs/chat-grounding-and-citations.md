# Chat grounding és citations

## Alapelv: AI nem keres

A chat LLM **nem** hív Qdrantot, DB-t vagy legacy retrieval API-t. A keresés determinisztikusan a `kb_search` pipeline-ban történik a válaszgenerálás **előtt**.

## Context típusok

| Típus | Használat | Bizonyíték? |
|-------|-----------|-------------|
| Conversation history | Kérdés értelmezése (follow-up) | Nem |
| Search evidence (`context_blocks`) | Válasz tartalma | Igen |
| Base prompt / channel policy | Stílus, nyelv, safety | Nem |

## Citation modell

Minden promptba kerülő evidence blokkhoz `CIT-n` azonosító tartozik. A válasz forráslistája a `kb_search_citations` és `sources` mezőkből épül.

### Download mezők

| Mező | Jelentés |
|------|----------|
| `download_ref` | Belső referencia (`source:{chunk_id}`) |
| `download_url` | Konkrét API endpoint a letöltéshez |
| `download_url_template` | Sablon fallback dokumentációhoz |

A frontend elsődlegesen a `download_url`-t használja.

## No-evidence (`NO_ANSWER`)

- Fix üzenet: *„Nem találtam releváns választ…”*
- **Nincs** LLM hívás
- Response és snapshot: üres `sources`, `citations`, `context_blocks`
- Turn mentődik audit célból

## Readiness (`BLOCKED_NOT_READY`)

- Fix üzenet: *„A kiválasztott tudástár még nem kereshető…”*
- **Nincs** LLM hívás
- `readiness.blocking_issues` a blokkoló okok listája
- Debug/admin: `diagnostics_url` → `/api/kb/{kb_uuid}/indexing/diagnostics`

## Channel audit

`channel_id` formátum channel API-n: `{channel_type}:{credential_id}` (pl. `widget:12`).

## E2E checklist

`qa/chat-search-e2e-checklist.md`

## Audit

- `query_run_id` — minden keresés
- `chat_turn_context_snapshots` — prompt + search context snapshot turnönként
- Backend session: `conversation_id` + `chat_sessions` / `chat_turns`
