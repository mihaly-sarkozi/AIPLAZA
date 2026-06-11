# kb_maintenance

A tudástár hosszú távú karbantartása. A `kb_understanding` felé eseményekkel
indít újrafuttatást — közvetlen kereszt-import itt is tilos.

## Részei

```text
újraindexelés, újraembeddingelés, hibás item újrafuttatás,
elavult tartalom figyelés, duplikátum kezelés, cleanup
```

## Cél-szerkezet

```text
kb_maintenance/
├── module.py                        ✓ (skeleton)
├── bootstrap/
│   ├── dependencies.py
│   └── service_keys.py              ✓ (skeleton)
├── dto/
├── enums/
├── service/
│   ├── ReindexService.py
│   ├── ReembedService.py
│   ├── RetryFailedItemsService.py
│   ├── StaleContentMonitorService.py
│   ├── DeduplicationService.py
│   └── CleanupService.py
└── events/
```

## Fejlesztési sorrend (a teljes KB sorrendből)

kb_maintenance (16.)
