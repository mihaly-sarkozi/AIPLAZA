# kb_indexing

A feldolgozott tudás kereshetővé tétele. A `kb_understanding`-tól eseményen
(`indexing_requested`) keresztül kapja a chunkokat/embeddingeket/entitásokat.

**Szabály:** az indexelés külön modul, mert **írja** az indexeket; a keresés
(`kb_search`) külön modul, mert **olvassa** őket. Ez a modul nem szolgál ki keresést.

## Index-típusok

```text
full-text index, vector index, entity index, keyword index, metadata index, hybrid index
```

## Cél-szerkezet

```text
kb_indexing/
├── module.py                          ✓ (skeleton)
├── bootstrap/
│   ├── dependencies.py
│   └── service_keys.py                ✓ (skeleton)
├── dto/
├── enums/
├── service/
│   ├── IndexChunksService.py
│   ├── BuildFullTextIndexService.py
│   ├── BuildVectorIndexService.py
│   ├── BuildEntityIndexService.py
│   └── BuildHybridIndexService.py
├── repository/
│   ├── FullTextIndexRepository.py
│   ├── VectorIndexRepository.py
│   └── EntityIndexRepository.py
├── adapters/
│   ├── PgVectorAdapter.py
│   └── PostgresFullTextAdapter.py
└── events/
    ├── indexing_requested_handler.py
    └── indexing_completed_event.py
```

## Fejlesztési sorrend (a teljes KB sorrendből)

full-text (7.) → vector (9.)
