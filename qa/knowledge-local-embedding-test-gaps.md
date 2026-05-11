# Knowledge Local Embedding Test Gaps

Ez a dokumentum a BGE-M3 + lokális embedding + workeres indexelés előtti validációs hiányokat rögzíti.

## Meglévő erős lefedettség

- Query resolver + query-aware + synthesis unit szint.
- Knowledge facade regresszió (in-memory vector index).
- Ingest/progress összegző logika (unit szinten).
- Index build retry/recovery API helper logika.

## Kritikus hiányok

- Qdrant wrapper vector contract hiány:
  - `ensure_collection_schema(_async)` vector size szerződés
  - query vector és index vector dimenzió konzisztencia
  - embed/upsert útvonal explicit ellenőrzése
- Embedding provider contract hiány:
  - provider válasz dimenzió
  - üres/hibás válasz ágak
- Worker queue/pool contract hiány:
  - queue -> worker -> ready
  - retry/idempotencia
  - párhuzamossági limit
- Progress contract hiány:
  - állapotátmenetek kötelező mezői (`overall_percent`, `active_module`, `active_message`)
- Storage consistency hiány:
  - index build állapot és chunk_count perzisztencia
  - vektor payload minimál contract (build/source/profile mezők)

## Validációs cél

Az átállás előtti és utáni futtatásból bizonyítható legyen:

1. A kérdésmátrix regressziómentes.
2. A vektor méret és séma konzisztens.
3. A progress payload UI-kompatibilis.
4. A build perzisztencia és vektor payload szerződés stabil.
