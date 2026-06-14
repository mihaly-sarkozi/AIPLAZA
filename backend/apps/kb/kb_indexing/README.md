# kb_indexing

## Felelősség

Embedding vektorok + chunk + discovery bundle alapján **Qdrant payloadot épít** és **vector + payload upsert**et végez.
A kereséskor a Qdrant már kész, szűrhető payloadot ad vissza.

## Input event

- `kb.indexing_requested`
- Payload: `tenant_slug`, `knowledge_base_id`, `training_item_id`, `understanding_job_id`, `discovery_job_id`, `embedding_job_id`, `created_by`

## Output event

- `kb.indexing_completed` — siker vagy partial esetén (`status` mezővel)

## Táblák

- `kb_indexing_jobs` — indexelési futás
- `kb_indexed_chunks` — chunk ↔ Qdrant point mapping, payload/vector hash

## Qdrant payload szabály

Payload **indexing időben** épül (`BuildQdrantPayloadService`), upsert előtt.
Filterezhető mezők: `knowledge_base_id`, `training_item_id`, `language_code`, `content_type`, `topics`, `entities`, `overall_score`.
Teljes chunk text csak preview (`text_preview`, max ~500 char).

## Collection

- Név: knowledge base `qdrant_collection_name` (kb_crud)
- Distance: cosine
- Vector size: embedding model dimension
- Collection + payload indexek: `EnsureQdrantCollectionService`

## Idempotencia

- Ugyanarra az `embedding_job_id`-ra nem indul több aktív indexing job.
- Point ID: determinisztikus (`stable_point_id(chunk_id)`) → upsert, nem duplikáció.

## Issue kódok

`NO_EMBEDDINGS_FOR_INDEXING`, `QDRANT_COLLECTION_MISSING`, `QDRANT_DIMENSION_MISMATCH`, `QDRANT_UPSERT_FAILED`, `INDEX_PAYLOAD_BUILD_FAILED`, `MISSING_EMBEDDING`, `INDEXING_PARTIAL_FAILURE`

## Mit nem csinál

- Embedding generálás
- Discovery / understanding
- Payload építés search időben (kb_search csak olvas)

## Processing napló

INDEXING_*, QDRANT_* event típusok a közös processing rétegben.
