# kb_crud

Tudástár (KnowledgeBase) életciklus és jogosultság-kezelés: létrehozás, listázás,
lekérés, módosítás, törlés (soft delete), valamint a use/train felhasználói
jogosultságok kezelése. A korábbi `apps/knowledge` `/kb` CRUD + permission
végpontok teljes funkcionális utódja.

## Rétegek (kb_ingest minta, egy osztály = egy fájl)

| Könyvtár | Szerep |
|----------|--------|
| `orm/` | `KnowledgeBaseORM` (`knowledge_bases`), `KnowledgeBasePermissionORM` (`kb_user_permission`) — a kanonikus tábla definíciók |
| `domain/` | `KnowledgeBase` entitás + enumok (`KnowledgeBaseStatus`, `KbPermissionLevel`, `PersonalDataMode`, `PersonalDataSensitivity`, `CrudErrorCode`) |
| `dto/` | HTTP request/response modellek (`KnowledgeBaseResponse` = legacy `KBOut` paritás) |
| `validation/` | `ValidateKbName` |
| `errors/` | `CrudValidationError`, `CrudNotFoundError`, `CrudPermissionError`, `CrudLimitError` |
| `ports/` | Repository + külső függőség szerződések (cleanup, storage metrics, training summary, usage limit, user directory) |
| `adapters/` | Átmeneti legacy-delegáló adapterek (knowledge facade, platform usage, user repo) |
| `repository/` | `KnowledgeBaseRepository`, `KnowledgeBasePermissionRepository` (SQLAlchemy) |
| `service/` | Use-case osztályok: create/list/get/update/delete + permission get/batch/set + `KbAccessPolicy` + `KbCrudAuditLogger` |
| `mapper/` | ORM → domain leképezés |
| `router/` | `/kb` endpointok |
| `bootstrap/` | DI (`dependencies.py`, `service_keys.py`) és tenant séma hook (`tenant_hooks.py`) |
| `module.py` | registry bekötés |

## Endpointok

- `GET /api/kb` — lista (szerepkör szerinti szűrés, `can_train`, `has_training`, `storage_metrics`)
- `POST /api/kb` — létrehozás (csak owner, usage limit, induló permissionök)
- `GET /api/kb/{kb_id}` — lekérés (use/train joggal)
- `PUT /api/kb/{kb_id}` — módosítás (train joggal; personal_data/pii/public mezők)
- `DELETE /api/kb/{kb_id}` — törlés (csak owner, `confirm_name`, tartalom ürítés, soft delete)
- `GET /api/kb/{kb_id}/permissions` — jogosultság lista (train joggal)
- `PUT /api/kb/{kb_id}/permissions` — jogosultságok beállítása (saját jog nem vonható vissza)
- `POST /api/kb/permissions/batch` — több tudástár jogosultságai (max 100 uuid)
