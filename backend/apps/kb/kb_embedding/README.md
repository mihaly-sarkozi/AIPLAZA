# kb_embedding

## Felelősség

A discovery után **csak embedding vektorokat** készít és tárol Postgresben (`kb_embeddings`).
Nem ír Qdrantba, nem épít keresési payloadot.

## Input event

- `kb.embedding_requested`
- Payload: `tenant_slug`, `knowledge_base_id`, `training_item_id`, `understanding_job_id`, `discovery_job_id`, `created_by`

## Output event

Siker vagy engedélyezett partial esetén:

- `kb.indexing_requested`
- Payload: fenti mezők + `embedding_job_id`

## Táblák

- `kb_embedding_jobs` — futás állapota (PENDING, RUNNING, COMPLETED, PARTIAL, FAILED)
- `kb_embeddings` — chunkonkénti vektor (`embedding_vector` JSONB), hash-ek, státusz

## Idempotencia

- Ugyanarra a `discovery_job_id`-ra nem indul több aktív job.
- Dedup kulcs: `knowledge_base_id` + `training_item_id` + `chunk_id` + `embedding_model` + `embedding_input_hash`.

## Embedding input szabály

Determinisztikus, válogatott discovery kontextus: chunk text, heading, content type, top keywords/topics/entities, process lépések.
Nem kerül bele: technikai ID-k, page numbers, score részletek, teljes relationship lista.

## Issue kódok

`NO_CHUNKS_FOR_EMBEDDING`, `MISSING_EMBEDDING`, `EMBEDDING_DIMENSION_MISMATCH`, `EMPTY_EMBEDDING_VECTOR`, `EMBEDDING_PROVIDER_FAILED`, `EMBEDDING_PARTIAL_FAILURE`

## Mit nem csinál

- Qdrant írás / payload építés
- Discovery / understanding lépések
- Keresés

## Processing napló

`kb_processing_events`, `kb_processing_issues`, `kb_processing_metrics` — EMBEDDING_* event típusokkal.
