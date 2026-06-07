# kb_crud

Tudástár (KnowledgeBase) életciklus: létrehozás, listázás, lekérés, módosítás, archiválás.

| Fájl | Szerep |
|------|--------|
| `schemas.py` | HTTP request/response DTO-k |
| `use_cases.py` | Üzleti műveletek (egy osztály / művelet) |
| `repository.py` | SQLAlchemy perzisztencia (`KBORM`) |
| `router.py` | `/kb` endpointok |
| `bootstrap/dependencies.py` | repository DI |
| `module.py` | registry bekötés |

Első működő endpointok: `POST /api/kb`, `GET /api/kb`, `GET /api/kb/{id}` (+ PUT/DELETE).
