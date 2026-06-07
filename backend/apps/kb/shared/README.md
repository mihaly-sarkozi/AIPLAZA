# shared

Közös típusok, hibák, eseménynevek, ID generálás — **nincs üzleti logika**.

| Fájl | Tartalom |
|------|----------|
| `types.py` | `NewType` aliasok (TenantId, KnowledgeBaseId, …) |
| `ids.py` | `new_id(prefix)` |
| `errors.py` | `KbError` és leszármazottak |
| `events.py` | queue/event név konstansok |
| `contracts.py` | modulok közötti adatátadás (`MaterialRef`, `SearchContextItem`) |
