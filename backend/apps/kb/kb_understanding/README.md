# kb_understanding — technikai tartalom-előkészítés

A betöltött anyag technikai előkészítése. A `kb_ingest`-től eseményen
(`UNDERSTANDING_REQUESTED`) kapja a nyers anyag referenciáját; siker esetén
`DISCOVERY_REQUESTED` eseménnyel indítja a `kb_discovery` feldolgozást.
Nem végez entitás/topic/embedding felismerést és nem ír keresőindexet.

## Extract réteg (part-alapú)

```text
INPUT → adapter → ExtractResult → ExtractedContent + ExtractedContentPart → trace
```

- Part típusok: `TEXT`, `TABLE`, `OCR_TEXT`, `OCR_EMPTY`, `OCR_FAILED`
- PDF: oldalankénti feldolgozás, táblázatok külön part, OCR fallback kevés szövegnél
- Konfiguráció: `config/ExtractConfig.py` (`MAX_FILE_SIZE_MB`, `MAX_PAGE_COUNT`, stb.)
- Normalize csak `TEXT` / `TABLE` / `OCR_TEXT` partokon dolgozik

## Pipeline (kötelezően külön lépések)

```text
1. extract              → ExtractContentService
2. normalize            → NormalizeContentService
3. structure detection  → DetectStructureService
4. chunking             → ChunkContentService
5. validation           → ValidateUnderstandingService
```

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
- Nincs LLM, nincs entitás/topic felismerés — az a `kb_discovery` feladata.

## Fejlesztési sorrend

extract → normalize → structure detection → chunking → validation → discovery
