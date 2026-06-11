# kb_testing

A teljes tudásfolyamat minőségének mérése — nem a pytest unit-tesztek helye,
hanem a pipeline kimeneteit minősítő szolgáltatások modulja.

**Szabály:** minden összetett pipeline-lépéshez tartozzon külön teszt.

## Tesztelendő szintek

```text
ingest teszt, extract teszt, normalize teszt, chunking teszt,
entity extraction teszt, embedding teszt, indexing teszt, search teszt,
ranking teszt, AI válasz teszt, forrásellenőrzés
```

Minden pipeline-lépésnél ellenőrizendő: mit kapott bemenetként, mit adott
kimenetként, mennyi ideig futott, hibázott-e, újrafuttatható-e, módosított-e adatot.

## Cél-szerkezet

```text
kb_testing/
├── module.py                        ✓ (skeleton)
├── bootstrap/
│   ├── dependencies.py
│   └── service_keys.py              ✓ (skeleton)
├── dto/
├── enums/
└── service/
    ├── PipelineStepQualityService.py
    ├── SearchQualityService.py
    ├── RankingQualityService.py
    ├── AnswerQualityService.py
    └── SourceVerificationService.py
```

## Fejlesztési sorrend (a teljes KB sorrendből)

kb_testing (15.)
