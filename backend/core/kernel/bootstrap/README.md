# core/kernel/bootstrap

## Feladat
A `bootstrap` könyvtár a kernel runtime összeszerelési rétege. Nem indít alkalmazást és nem szolgál ki HTTP kérést, hanem registryket, buildereket és modulregisztrációs szabályokat ad az `app` és `runtime` rétegeknek.

## Fájlok
- `infrastructure.py`: Felépíti a DB session factoryt, email service-t és core repository registryt.
- `infrastructure_registry.py`: Az infrastruktúra példányok stabil adatstruktúrája.
- `repository_registry.py`: A core repository példányok stabil adatstruktúrája.
- `security.py`: Felépíti a security registryt: clock, token service, security logger, audit/event channel és dispatcher.
- `modules.py`: A manifest modulregisztráció orchestrátora. Létrehozza a ModuleContextet és futtatja a core/app fázisokat.
- `module_phases.py`: A core és app modulregisztrációs fázisok végrehajtó helperjei.
- `module_validation.py`: A modul dependency boundary szabályainak validációja.
- `__init__.py`: Import-light csomaghatár, konkrét API-kat submodule-ból kell importálni.

## Kapcsolódás
Az `app/app_container.py` hívja az infrastruktúra buildet, a security assemblyt és a modulregisztrációt. A `runtime` wiring fájlok a registry típusokat kapják meg, és ezekből kötnek DI-t, permission service-t, outbox workert és lifecycle kontrollert. A standalone worker entrypoint is a bootstrap infrastruktúra- és security-buildereket használja, hogy web process nélkül is ugyanazt a runtime alapot kapja.

## Fontos elv
A bootstrap réteg épít és validál, de nem futtat hosszú életű folyamatot. A folyamatok indítása és leállítása a `runtime` és `app_lifespan` felelőssége.

## Sárközi Mihály - 2026.05.21
