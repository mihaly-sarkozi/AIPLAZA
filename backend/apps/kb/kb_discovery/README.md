# kb_discovery — lokális tudás-felfedezés

A `kb_discovery` modul a chunkokból determinisztikus, LLM-mentes felismerést végez:
nyelvfelismerés, entitások, lokális enrichment, kapcsolatok és pontszám.

## Pipeline

```text
LANGUAGE_DETECTION → ENTITY_EXTRACTION → LOCAL_KNOWLEDGE_ENRICHMENT
→ RELATIONSHIP_BUILD → KNOWLEDGE_SCORING → VALIDATION
```

## Támogatott nyelvek

- `hu`, `en`, `es` (+ `unknown`) — magyar, angol, spanyol
- Nyelvspecifikus stopword / keyword / topic szabályok: `languages/`

## Események

- Bemenet: `kb.discovery_requested` (understanding siker után)
- Kimenet siker esetén: `kb.discovery_completed` + `kb.embedding_requested`

## Szabályok

- Nincs LLM — csak regex, dictionary, alias, heurisztika
- Nincs szintaktikai NLP pipeline (Stanza / spaCy / UDPipe nincs bekötve)
- `GivenNameRecognizer`: csak gyenge candidate (0.35), önmagában nem persistál PERSON entity-t
- `FullPersonNameRecognizer` + directory alias: teljes név / directory találat mentésre kerül (≥ 0.5)
- Person mention szűrés: longest-match; teljes név nyer az átfedő aliasok felett
- `ProductRecognizer` törölve — product típus a `DictionaryEntityRecognizer`-en keresztül jön
- `CompanyNameRecognizer` törölve — helyette `LegalFormCompanyRecognizer`
- Entitás/enrichment/relationship/score tulajdonosa: `kb_discovery`
- Meglévő táblanevek kompatibilitás miatt megmaradhatnak (`kb_entities`, `kb_enrichments`, stb.)

## Tenant / KB adatfájlok

Példa fájlok a `data/` alatt:

- `dictionaries/tenants/{tenant_slug}.json`
- `dictionaries/knowledge_bases/{knowledge_base_id}.json`
- `systems/tenants/{tenant_slug}.json`
- `systems/knowledge_bases/{knowledge_base_id}.json`
- `persons/tenants/{tenant_slug}.json`
- `persons/knowledge_bases/{knowledge_base_id}.json`
