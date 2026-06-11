# kb_services

A tudástárra épülő üzleti szolgáltatások. Minden szolgáltatás a `kb_search`,
`kb_understanding`, `kb_feedback` és `kb_indexing` **eredményeire** épül —
**nem végezhet nyers dokumentumfeldolgozást**.

A szolgáltatások alapja a feldolgozott tudásréteg:

```text
chunks, entities, relationships, summaries, keywords, topics, scores,
search_events, feedback
```

## Szolgáltatások

```text
vázlatkészítő, betanítási modul, témaösszefoglaló, kérdés-válasz,
hiánylista, statisztika, folyamatkinyerő, tudástérkép
```

## Cél-szerkezet

```text
kb_services/
├── module.py                          ✓ (skeleton)
├── bootstrap/
│   ├── dependencies.py
│   └── service_keys.py                ✓ (skeleton)
├── router/
│   └── KnowledgeServicesRouter.py
├── dto/
├── service/
│   ├── OutlineService.py
│   ├── OnboardingMaterialService.py
│   ├── TopicSummaryService.py
│   ├── QuestionAnswerService.py
│   ├── GapAnalysisService.py
│   ├── StatisticsService.py
│   ├── ProcessExtractionService.py
│   └── KnowledgeMapService.py
└── mapper/
    └── service_response_mapper.py
```

## Fejlesztési sorrend (a teljes KB sorrendből)

question-answer (13.)
