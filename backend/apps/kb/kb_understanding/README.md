# kb_understanding

A betöltött anyag megértése és feldolgozása. A `kb_ingest`-től eseményen
(`UNDERSTANDING_REQUESTED`) keresztül kapja a nyers anyag referenciáját, a kimenetét
(`chunks + embeddings + entities + relationships + scores`) a `kb_indexing` felé
eseménnyel adja tovább. Nem ír keresőindexet és nem szolgál ki keresést.

## Pipeline (kötelezően külön lépések)

```text
1. extract              → ExtractContentService
2. normalize            → NormalizeContentService
3. structure detection  → DetectStructureService
4. chunking             → ChunkContentService
5. entity extraction    → ExtractEntitiesService
6. knowledge enrichment → EnrichKnowledgeService
7. embedding            → EmbedChunksService
8. relationship build   → BuildRelationshipsService
9. knowledge scoring    → ScoreKnowledgeService
10. validation          → ValidateUnderstandingService
```

Minden lépésnek saját bemenete, kimenete, státusza, hibakezelése, tesztje és
naplózható eredménye van. Az `UnderstandingPipelineService` csak összefűzi a lépéseket —
nem abban van a logika. Lépéshiba esetén az item `FAILED` / `PARTIAL` / `RETRYABLE`.

A kanonikus státuszok és lépések már megvannak: `enums/UnderstandingStatus.py`,
`enums/UnderstandingStep.py`.

## Cél-szerkezet

```text
kb_understanding/
├── module.py                              ✓ (skeleton)
├── bootstrap/
│   ├── dependencies.py
│   ├── service_keys.py                    ✓ (skeleton)
│   └── tenant_hooks.py
├── router/
│   └── UnderstandingRouter.py
├── dto/
│   ├── UnderstandingJobRequest.py
│   ├── UnderstandingJobResponse.py
│   ├── UnderstandingStepResult.py
│   └── UnderstandingStatusResponse.py
├── enums/
│   ├── UnderstandingStatus.py             ✓
│   ├── UnderstandingStep.py               ✓
│   ├── ChunkType.py
│   ├── EntityType.py
│   └── UnderstandingErrorCode.py
├── orm/
│   ├── UnderstandingJob.py
│   ├── UnderstandingStepRun.py
│   ├── ExtractedContent.py
│   ├── NormalizedContent.py
│   ├── KnowledgeChunk.py
│   ├── KnowledgeEntity.py
│   ├── KnowledgeRelationship.py
│   └── KnowledgeScore.py
├── repository/
│   ├── UnderstandingJobRepository.py
│   ├── ContentRepository.py
│   ├── ChunkRepository.py
│   ├── EntityRepository.py
│   ├── RelationshipRepository.py
│   └── ScoreRepository.py
├── service/
│   ├── StartUnderstandingService.py
│   ├── ExtractContentService.py
│   ├── NormalizeContentService.py
│   ├── DetectStructureService.py
│   ├── ChunkContentService.py
│   ├── ExtractEntitiesService.py
│   ├── EnrichKnowledgeService.py
│   ├── EmbedChunksService.py
│   ├── BuildRelationshipsService.py
│   ├── ScoreKnowledgeService.py
│   ├── ValidateUnderstandingService.py
│   ├── UnderstandingPipelineService.py
│   └── ProcessingTraceService.py
├── adapters/
│   ├── PdfExtractorAdapter.py
│   ├── DocxExtractorAdapter.py
│   ├── TextExtractorAdapter.py
│   ├── EmbeddingProviderAdapter.py
│   └── LlmEnrichmentAdapter.py
├── validation/
│   ├── ValidateExtractedContent.py
│   ├── ValidateChunks.py
│   ├── ValidateEntities.py
│   └── ValidateEmbeddings.py
├── mapper/
│   ├── understanding_mapper.py
│   ├── chunk_mapper.py
│   └── entity_mapper.py
└── events/
    ├── understanding_requested_handler.py
    ├── understanding_completed_event.py
    └── indexing_requested_event.py
```

## Szabályok

- Bizonyíték: minden chunk/tudáselem hordozza a kötelező forrás-metaadatokat
  (`source_id, document_id, chunk_id, checksum, version, page_number/section, …`).
- Idempotencia: ugyanarra az inputra ugyanazt vagy kompatibilis eredményt adja.
- Új extractor/embedder = új adapter, a pipeline nem módosul.
- Observability / trace itt él (`ProcessingTraceService`) — nem külön globális modul.

## Fejlesztési sorrend (a teljes KB sorrendből)

extract (3.) → normalize (4.) → structure detection (5.) → chunking (6.)
→ embedding (8.) → entity extraction (11.) → enrichment (12.)
