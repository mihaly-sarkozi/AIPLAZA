# core/kernel/runtime

A `runtime` könyvtár az AppContainer futásidejű összerakását és a process-szintű runtime döntéseket tartalmazza. Ide tartozik a clock dependency, az instance role kezelés, valamint azok a wiring modulok, amelyek a bootstrap eredményeit működő runtime komponensekké kapcsolják össze.

## Fő felelősség

Ez a réteg nem deklarál app modul szerződéseket és nem épít FastAPI appot. A feladata az, hogy az infrastruktúra, security, permission, outbox worker, module registry és lifecycle komponensek futásidőben össze legyenek kötve az `AppContainer` számára.

## Fájlok

- `__init__.py`: csomagjelölő; nincs eager export, hogy az assembly importok ne húzzanak be felesleges függőségeket.
- `clock.py`: közös Clock/SystemClock és UTC idő helper re-export, public runtime dependencyként.
- `instance_role.py`: `INSTANCE_ROLE` és worker loop env flag alapján process szerepkör döntések.
- `security_wiring.py`: AuditService, outbox repository és SecurityRegistry assembly.
- `outbox_wiring.py`: OutboxWorker példány építése settingsből és security registryből.
- `permission_wiring.py`: PermissionService összeállítása manifest permissionökből.
- `kernel_di_wiring.py`: gyakori platform service-ek bekötése a kernel dependency façade-ba.
- `module_registration.py`: manifest modulok runtime regisztrációja kezdeti lifecycle state-tel.
- `runtime_lifecycle.py`: runtime storage inicializálás, embedded worker indítás és shutdown koordináció.

## Kapcsolódás a nagy egészhez

Az `app/app_container.py` innen hívja az assembly lépéseket. A `bootstrap` réteg előállítja az infrastruktúra és security registry alapjait, a `runtime` pedig összeköti őket működő process komponensekké. Az `events` worker és az auth többpéldányos guardjai is innen kapják a lifecycle belépési pontot.

## Miért itt van a `clock.py`?

A `clock.py` általános runtime dependency, nem konfiguráció és nem domain logika. Core, app, ORM modellek és tesztek is innen importálják az időkezelést, így jó helyen van a `runtime` alatt, nem a kernel főkönyvtárban. Public API-ként engedélyezett, mert az időkezelés tesztelhetősége közös framework igény.

# Sárközi Mihály - 2026.05.21