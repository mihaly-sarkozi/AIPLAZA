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

## No-evidence

Ha nincs releváns találat: `answer_mode=NO_ANSWER`, fix üzenet, **nincs** LLM hallucináció.

## Readiness

Ha a tudástár nem kereshető: `answer_mode=BLOCKED_NOT_READY`, nincs AI válasz.

## Audit

- `query_run_id` — minden keresés
- `chat_turn_context_snapshots` — prompt + search context snapshot turnönként
- Backend session: `conversation_id` + `chat_sessions` / `chat_turns`
