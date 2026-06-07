# kb_reading — beolvasás

A **kb_reading** modul felelőssége: **fájl** és **URL** nyers anyag átvétele, validálás, raw storage-ba mentés, futás nyomon követése, duplikátum- és batch-szabályok, majd **understanding_requested** esemény kibocsátása.

A **szöveges tanítás** a **`kb_training`** modulban van (`POST /api/kb/{kb_id}/training/text`).

---

## HTTP végpontok

Prefix: `/api/kb`

| Metódus | Útvonal | Leírás |
|---------|---------|--------|
| `POST` | `/{kb_id}/ingest/files/estimate` | Fájl becslés (nincs run) |
| `POST` | `/{kb_id}/ingest/files` | Fájl beolvasás (multipart) |
| `POST` | `/{kb_id}/ingest/urls` | URL beolvasás |
| `GET` | `/{kb_id}/ingest/runs` | Futások listája |
| `GET` | `/ingest/runs/{run_id}` | Futás részletei |
| `GET` | `/ingest/items/{item_id}/raw` | Nyers tartalom letöltése |

Minden route: `Depends(require_permission("kb.train"))`.

---

## Modul szerkezet

```
kb_reading/
  module.py
  bootstrap/
  domain/
  dto/
  mapper/
  orm/              # ReadingBatch, ReadingItem, ReadingEvent
  ports/
  repository/
  router/
  service/
  storage/
  security/
  validation/
  adapters/
  support/
```

---

## Határok

- **Nem** chunking, embedding, indexelés — az **kb_understanding** feladata.
- **Nem** szöveges tanítás — az **kb_training** feladata.
- Más kb almodul import **tilos** (lásd `tests/unit/kb/test_import_boundaries.py`).
