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

## Lokális embedding provider (default)

Production default: `embedding_provider=local` valódi **sentence-transformers** modellel.

**Default modell:** `BAAI/bge-m3` (multilingual — magyar / angol / spanyol).

Alternatívák (configból):

- `intfloat/multilingual-e5-large`
- `sentence-transformers/paraphrase-multilingual-mpnet-base-v2`

A `LocalEmbeddingAdapter` **nem** használ dummy fallbacket. Modell betöltési vagy generálási hiba esetén a job `FAILED` / `PARTIAL`, és processing issue nyílik.

### Konfiguráció (env)

| Env változó | Default | Leírás |
|-------------|---------|--------|
| `EMBEDDING_PROVIDER` | `local` | `local`, `openai`, vagy `dummy` (dev only) |
| `EMBEDDING_MODEL` | `BAAI/bge-m3` | HuggingFace modell azonosító |
| `EMBEDDING_DEVICE` | `cpu` | `cpu`, `cuda`, `mps` |
| `EMBEDDING_BATCH_SIZE` | `16` | Batch méret encode során |
| `EMBEDDING_NORMALIZE` | `true` | Normalizált vektorok |
| `EMBEDDING_VECTOR_SIZE` | `1024` | Elvárt dimenzió (ellenőrzött) |
| `EMBEDDING_ALLOW_DUMMY` | `false` | Dummy provider engedélyezése |
| `EMBEDDING_MODEL_CACHE_DIR` | *(üres)* | Lokális modell cache útvonal |

A `KB_EMBEDDING_*` prefixű env aliasok is elfogadottak (pl. `KB_EMBEDDING_PROVIDER`).

### Dummy provider (csak fejlesztés)

- `embedding_provider=dummy` csak ha `embedding_allow_dummy=true` **és** nem production.
- Productionben `dummy` és `embedding_allow_dummy=true` **tilos** (startup guard).

### Modell cache / offline

Ha `EMBEDDING_MODEL_CACHE_DIR` meg van adva (pl. `/models/sentence-transformers`), a modell innen töltődik vagy ide cache-el.
Production runtime alatt nem szükséges internet, ha a modell előre letöltve van.

### Batch feldolgozás

`texts → batch split (EMBEDDING_BATCH_SIZE) → model.encode(batch) → vectors`

### Dimenzió ellenőrzés

Minden vektor hossza = `EMBEDDING_VECTOR_SIZE`. Eltérés esetén chunk `FAILED`, issue: `LOCAL_EMBEDDING_DIMENSION_MISMATCH`.

### metadata_json

Sikeres mentéskor:

```json
{
  "provider": "local",
  "model": "BAAI/bge-m3",
  "device": "cpu",
  "normalized": true,
  "batch_size": 16
}
```

## Issue kódok

Általános: `NO_CHUNKS_FOR_EMBEDDING`, `MISSING_EMBEDDING`, `EMBEDDING_DIMENSION_MISMATCH`, `EMPTY_EMBEDDING_VECTOR`, `EMBEDDING_PROVIDER_FAILED`, `EMBEDDING_PARTIAL_FAILURE`

Lokális provider: `LOCAL_EMBEDDING_MODEL_LOAD_FAILED`, `LOCAL_EMBEDDING_GENERATION_FAILED`, `LOCAL_EMBEDDING_DIMENSION_MISMATCH`

## Processing események

`EMBEDDING_*` és lokális provider események a közös `kb_processing_events` táblában:

- `LOCAL_EMBEDDING_MODEL_LOADING_STARTED` / `COMPLETED`
- `LOCAL_EMBEDDING_BATCH_STARTED` / `COMPLETED`
- `LOCAL_EMBEDDING_GENERATION_FAILED`

## Mit nem csinál

- Qdrant írás / payload építés
- Discovery / understanding lépések
- Keresés

## Processing napló

`kb_processing_events`, `kb_processing_issues`, `kb_processing_metrics`.
