# apps/chat/service

A `service` könyvtár a chat modul use-case és application service rétege. A `ChatService` jelenleg még kompatibilitási belépési pont, de az új felelősségeket fokozatosan külön service-ekbe kell vinni.

## Service Boundaryk

- `prompt_builder.py`: system prompt, conversation/retrieval history context, PII prompt policy és prompt-context debug payload összeállítása. Mellékhatásmentes, izoláltan tesztelendő boundary.
- `pii_depersonalization.py`: KB-szintű PII tokenizálás, maszkolás és visszahelyettesítés.
- `llm_budget.py`: LLM request, prompt és token budget kontroll.
- `chat_service.py`: legacy kompatibilitási orchestrator; új felelősséget csak delegálással kapjon.

## Következő Bontási Célok

Következőként a `RetrievalContextBuilder`, `LLMAnswerService`, `AnswerPostProcessor`, `SessionPacingService`, `CredentialAuthService` és `ChatTelemetryService` boundaryket érdemes kivezetni. A cél, hogy az endpoint orchestration és a provider/telemetry/policy side effectek külön tesztelhetők legyenek.

## Sárközi Mihály - 2026.05.22
