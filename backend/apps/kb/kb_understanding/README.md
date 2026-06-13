# kb_understanding — dokumentumtechnikai feldolgozás

A betöltött anyag technikai előkészítése. A `kb_ingest`-től eseményen
(`UNDERSTANDING_REQUESTED`) kapja a nyers anyag referenciáját; siker esetén
`DISCOVERY_REQUESTED` eseménnyel indítja a `kb_discovery` feldolgozást.

Ez a modul **nem** vég el entitásfelismerést, enrichmentet, embeddinget,
relationship építést, scoringot vagy keresőindexelést — azok a
`kb_discovery`, `kb_embedding`, `kb_indexing` modulok feladatai.

## Flow

```text
raw input
  → EXTRACT
  → NORMALIZE
  → CHUNKING
  → VALIDATION
  → READY_FOR_DISCOVERY
  → kb.discovery_requested
```

## Extract réteg (part-alapú, nagy fájl támogatás)

```text
stat → stratégia → IN_MEMORY | TEMP_FILE | STREAMING
  → adapter (path/bytes) → batch part mentés → trace
```

- Stratégiák: `IN_MEMORY` (≤20MB), `TEMP_FILE` (≤200MB), `STREAMING` (>200MB)
- Elutasítás: `> MAX_EXTRACT_FILE_SIZE_MB` → `FILE_REJECTED`
- FileStorage: `stat_bytes`, `materialize_to_temp_file`, `open_stream`
- Progress: job metadata `extract_progress` (25 oldalenként)

## OCR (Tesseract)

Az OCR a PDF oldalak képi tartalmára és a DOCX beágyazott képeire fut
(`hun+eng+spa`). A text layerrel megegyező OCR szöveg deduplikálódik.

### Python függőségek

- `pytesseract`, `Pillow` — OCR futtatás
- `pdfplumber`, `pypdfium2` — PDF text/kép kinyerés
- `python-docx` — DOCX beágyazott képek

### Rendszerfüggőség (kötelező)

A `pytesseract` önmagában nem elég; telepíteni kell a Tesseract binary-t és
nyelvi csomagokat:

```bash
apt-get update
apt-get install -y \
  tesseract-ocr \
  tesseract-ocr-hun \
  tesseract-ocr-eng \
  tesseract-ocr-spa
```

A `docker/backend.Dockerfile` és `docker/backend.prod.Dockerfile` tartalmazza.

### Config (env)

| Változó | Alapértelmezés |
|---------|----------------|
| `OCR_ENABLED` | `true` |
| `OCR_LANGUAGES` | `hun+eng+spa` |
| `OCR_MIN_CONFIDENCE` | `0.50` |
| `OCR_DEDUPLICATE` | `true` |
| `OCR_RUN_ON_PDF_IMAGES` | `true` |
| `OCR_RUN_ON_DOCX_IMAGES` | `true` |
| `OCR_RUN_ON_LOW_TEXT_PDF_PAGES` | `true` |
| `OCR_MAX_IMAGE_PIXELS` | `20000000` |
| `OCR_TIMEOUT_SECONDS` | `120` |

Ha a Tesseract vagy nyelvi csomag hiányzik, az extract pipeline nem áll le;
`OCR_FAILED` part keletkezik (`ocr_engine_unavailable` / `ocr_language_pack_missing`).

## Pipeline (kötelezően külön lépések)

```text
1. extract              → ExtractContentService
2. normalize            → NormalizeContentService
3. chunking             → ChunkContentService (normalized parts → chunks)
4. validation           → ValidateUnderstandingService
```

A chunking a `kb_normalized_content_parts` rekordokból dolgozik; a blokktípus-felismerés
belső `NormalizedPartBlockClassifier` helperrel történik, külön DB réteg nélkül.

Minden lépésnek saját bemenete, kimenete, státusza, hibakezelése, tesztje és
naplózható eredménye van. Az `UnderstandingPipelineService` csak összefűzi a lépéseket.

A kanonikus státuszok: `enums/UnderstandingStatus.py` (`READY_FOR_DISCOVERY` terminális siker).

## Cél-szerkezet

```text
kb_understanding/
├── module.py
├── bootstrap/
├── dto/
├── enums/
├── errors/
├── events/
├── orm/
├── repository/
├── service/
├── validation/
├── mapper/
├── adapters/
└── router/
```

## Szabályok

- Bizonyíték: minden chunk hordozza a kötelező forrás-metaadatokat.
- Idempotencia: ugyanarra az inputra ugyanazt vagy kompatibilis eredményt adja.
- Új extractor = új adapter, a pipeline nem módosul.
- A modul zárt: csak extract → normalize → chunk → validation.

## Fejlesztési sorrend

extract → normalize → chunking → validation → discovery (külön modul)
