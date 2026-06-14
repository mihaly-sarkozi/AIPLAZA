# Chat modul

Production chat orchestration: session, retrieval wiring, grounding, LLM, citations.

## Flow

1. `ChatWithSourcesService.build()` — session + retrieval + LLM + grounding
2. `RetrievalContextBuilder` — elsődlegesen `KbSearchChatFacade` (`CHAT_USE_KB_SEARCH=true`)
3. `AnswerGroundingValidator` — no-evidence / not-ready / answered
4. `ChatSessionService` — `chat_sessions`, `chat_turns`, `chat_turn_context_snapshots`

## Answer modes

| Mode | Viselkedés |
|------|------------|
| `ANSWERED` | Van evidence, LLM válasz (vagy direct knowledge) |
| `NO_ANSWER` | Nincs releváns találat — fix üzenet, nincs LLM, üres sources |
| `BLOCKED_NOT_READY` | KB nem kereshető — fix üzenet, nincs LLM, readiness payload |
| `LLM_ERROR` | Retrieval OK, de LLM provider hiba |

## Channel audit

- Web: `channel_id=web`, metadata: `{channel_type, source: web_chat}`
- Channel API: `channel_id={type}:{credential_id}`, metadata: `{channel_type, channel_credential_id, external_session_id, source: channel_api}`

Metadata mentés: `chat_sessions.metadata_json`.

## Source download

- API response `sources[].download_url` — konkrét endpoint (elsődleges)
- `download_ref` — belső referencia (`source:{chunk_id}`)
- Fallback template: `/api/chat/sources/{query_run_id}/{source_id}/download`

### `/api/chat/sources/{query_run_id}/{source_id}/download`

Jelenleg **evidence / citation export**: a válaszhoz tartozó citation rekord szöveges kiexportálása
(citation id, dokumentum cím, oldal, szekció, snippet). **Nem** az eredeti feltöltött fájl letöltése.

Ha később szükséges az eredeti dokumentum letöltése (PDF/DOCX stb.), arra külön endpoint készül.

## Response mezők

- `sources[]` — UI-barát forráslista (`ChatSourceItem`: citation_id, download_url, page_numbers, …)
- `citation_records[]` — opcionális teljes citation objektumlista a frontend számára
- `citations[]` — citation id string lista (kompatibilitás)

## E2E checklist

Lásd: `qa/chat-search-e2e-checklist.md`
