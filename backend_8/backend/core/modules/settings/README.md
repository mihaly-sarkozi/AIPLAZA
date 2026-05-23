# core/modules/settings

A `settings` modul a tenantonként perzisztált platform beállítások központi modulja. Kétfaktoros auth flaget, időzóna és dátum/idő formátum beállításokat, billing profil mezőket, valamint a settings felület modulok által bővíthető section registryjét kezeli.

## Fő felelősség

A modul kulcs-érték alapú tenant settings táblát telepít és kezel. A `SettingsService` validált olvasási/frissítési API-t ad más platform moduloknak, például az auth modulnak a kétfaktoros beállítás olvasásához, az app settings felületnek pedig a teljes beállítás snapshot és update műveletekhez.

## Rétegek

- `settings.py`: `SettingsCoreModule`, amely regisztrálja a repositoryt, service-t, core settings sectiont és tenant schema hookot.
- `domain/`: `SettingsORM`, a tenant schema `settings` táblájának SQLAlchemy modellje.
- `repository/`: kulcs szerinti olvasás és upsert a settings táblába.
- `service/`: validált settings use case-ek, default értékek és audit események.
- `registry/`: app és core modulok által bővíthető settings section registry.
- `tenant_hooks.py`: tenant schema telepítés és idempotens audit oszlop migráció.

## Kapcsolódás a nagy egészhez

Az `AppManifest` core platform modulként tölti be a `SettingsCoreModule`-t. A modul `PLATFORM_SETTINGS_REPOSITORY` és `PLATFORM_SETTINGS_SERVICE` kulcsokon publikálja a komponenseit, a tenant provisioning pedig a `register_settings_tenant_hooks` hookon keresztül telepíti a táblát. Az `apps/settings` API és más app modulok a registryből listázzák a megjeleníthető settings sectionöket.

## Sárközi Mihály - 2026.05.21
