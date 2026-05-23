# core/infrastructure/audit

Az `audit` infrastruktúra modul a platform közös audit naplózási adaptere. Tenant-sémás `audit_log` táblába ír audit eseményeket, közös action enumot ad, sanitizálja a details payloadot, és correlation id-t kapcsol az eseményekhez.

## Fő felelősség

A modul célja, hogy auth, users, settings, brand, tenant signup/provisioning, admin és event-driven folyamatok egységes audit trailt írjanak. Az `AuditService` szinkron módon delegál az append-only repositoryra, ezért tranzakciós use case-eknél közvetlenül és előre láthatóan viselkedik.

## Rétegek

- `const/audit_log_action_const.py`: stabil `AuditLogAction` enum a platform audit eseményekhez.
- `models/audit_log_orm.py`: tenant schema `audit_log` SQLAlchemy modell.
- `repositories/audit_log_repository.py`: append-only perzisztencia adapter JSON details serializálással.
- `service/audit_service.py`: default outcome/target/actor számítás, correlation id illesztés és sanitizálás.
- `tenant_hooks.py`: tenant schema hook az audit_log tábla és indexek telepítéséhez.
- `__init__.py`, `models/__init__.py`, `repositories/__init__.py`, `service/__init__.py`: könnyű/lazy exportfelületek.

## Kapcsolódás a nagy egészhez

A bootstrap réteg `AuditLogRepository` és `AuditService` példányokat köt az app containerbe. A users modul tenant hookjai regisztrálják az audit tenant schema hookot, így minden tenant schema megkapja az `audit_log` táblát. Több core és app-facing modul közvetlenül importálja az `AuditLogAction` enumot, ezért az action nevek stabil contractnak számítanak.

## Infrastruktúra Jelleg

Ez core infrastruktúra komponens, nem üzleti modul. A konkrét audit eseményeket az auth, users, settings, brand, tenant, admin és event folyamatok indítják, de az írás, storage contract és sanitizálás közös infrastruktúra-felelősség.

## Kockázatok

Az audit service szinkron DB írást végez, ezért hívási helytől függően hatással lehet tranzakciós use case-ekre. Az `AuditLogAction` enum bővítése biztonságos, de meglévő action átnevezése teszteket, dashboardokat és audit kereséseket törhet. A `details` mezőbe kerülő adatot mindig sanitizálva kell hagyni.

## Sárközi Mihály - 2026.05.21
