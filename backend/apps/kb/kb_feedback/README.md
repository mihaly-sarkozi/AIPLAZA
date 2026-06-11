# kb_feedback

Felhasználói visszajelzések és használati jelek gyűjtése.

## Gyűjtött jelek

```text
hasznos / nem hasznos, kattintás, keresési esemény, AI válasz értékelés,
hiányzó találat jelzés, komment
```

Ezek később hatással lehetnek: rankingre, hiánylistára, statisztikára,
karbantartásra — a fogyasztók (`kb_search`, `kb_services`, `kb_maintenance`)
shared contracts/events útján olvassák az eredményt.

## Cél-szerkezet

```text
kb_feedback/
├── module.py                        ✓ (skeleton)
├── bootstrap/
│   ├── dependencies.py
│   ├── service_keys.py              ✓ (skeleton)
│   └── tenant_hooks.py
├── router/
│   └── FeedbackRouter.py
├── dto/
├── enums/
├── orm/
├── repository/
│   └── SearchEventRepository.py
└── service/
```

## Fejlesztési sorrend (a teljes KB sorrendből)

kb_feedback (14.)
