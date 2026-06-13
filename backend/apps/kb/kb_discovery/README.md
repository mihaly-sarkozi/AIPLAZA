# kb_discovery — lokális tudás-felfedezés

A `kb_discovery` modul a chunkokból determinisztikus, LLM-mentes felismerést végez:
nyelvfelismerés, entitások, lokális enrichment, kapcsolatok és pontszám.

## Pipeline

```text
LANGUAGE_DETECTION → ENTITY_EXTRACTION → LOCAL_KNOWLEDGE_ENRICHMENT
→ RELATIONSHIP_BUILD → KNOWLEDGE_SCORING → VALIDATION
```

## Támogatott nyelvek

- `hu`, `en`, `de` (+ `unknown`)
- Nyelvspecifikus stopword / keyword / topic szabályok: `languages/`

## Események

- Bemenet: `kb.discovery_requested` (understanding siker után)
- Kimenet siker esetén: `kb.discovery_completed` + `kb.embedding_requested`

## Szabályok

- Nincs LLM — csak regex, dictionary, alias, heurisztika
- Entitás/enrichment/relationship/score tulajdonosa: `kb_discovery`
- Meglévő táblanevek kompatibilitás miatt megmaradhatnak (`kb_entities`, `kb_enrichments`, stb.)
