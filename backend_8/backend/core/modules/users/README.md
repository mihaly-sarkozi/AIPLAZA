# core/modules/users

A `users` modul a platform felhasználókezelési capability-je. User domain DTO-kat és ORM modelleket, admin CRUD-ot, self-service profil és `/auth/me` végpontokat, meghívásos regisztrációt, jelszóbeállítást, user cache-t, repositorykat és tenant schema hookokat fog össze.

## Fő felelősség

A modul biztosítja a tenant-sémás felhasználói perzisztenciát és az erre épülő alkalmazási műveleteket. A `UserService`, `UserProfileService` és `InviteService` kezeli a user CRUD-ot, profilfrissítést, jelszófolyamatokat, meghívó tokeneket, auditot, cache invalidációt és auth/session kapcsolódásokat.

## Rétegek

- `users.py`: `UsersCoreModule`, amely a users feature containert, service kulcsokat, routereket és tenant hookokat regisztrálja.
- `container/`: UserRepository, InviteTokenRepository, UserService, UserProfileService és InviteService összekötése.
- `domain/dto/`: stabil `User` és `InviteToken` adatcontractok, amelyeket auth, tenant, app modulok és tesztek is használnak.
- `domain/models/`: tenant-sémás `users` és `user_invite_tokens` SQLAlchemy modellek.
- `domain/policies/`: profile locale/theme és login security/lockout döntési szabályok.
- `repository/persistence/`: users és invite token SQLAlchemy repository adapterek.
- `service/`: user CRUD, profile, invite, jelszó és forgot-password application logika.
- `router/`: admin users, profile/self-service és invite HTTP endpointok.
- `router/requests` és `router/responses`: Pydantic HTTP modellek.
- `web/presenters` és `web/helpers`: domain User DTO -> HTTP response prezentáció és profile helper importok.
- `cache/`: user cache szerializáció, JWT light-path user építés és cache invalidáció.
- `tenant_hooks.py`: users táblák és user mezők tenant schema telepítése/migrációja.

## Kapcsolódás a nagy egészhez

Az `AppManifest` core platform modulként tölti be a `UsersCoreModule`-t. A modul `PLATFORM_USERS_SERVICE`, profile és invite service kulcsokon publikálja a komponenseit; az auth modul a `User` DTO-ra, user cache-re és repositoryra épít, a tenant signup user provisioninghoz használja, az app modulok pedig current user contractként importálják.

## Boundary Döntés

A users modul indokoltan marad `core/modules/users` alatt. Bár több része stabil publikus integrációs felület, a felelőssége felhasználói domain és platform capability, nem általános kernel runtime. Kernelben csak a service key-ek, route assembly és dependency registry jellegű elemek vannak jó helyen.

## Publikus Integráció

A `core.kernel.interface.public_api` engedi több users import használatát app modulokból, például `core.modules.users.domain.dto`, `UserORM` és `UserRepository` útvonalakat. Ezeket stabil szerződésként kell kezelni: mező- vagy viselkedésváltoztatás széles körben érintheti az auth, tenant, billing, profile, knowledge és chat modulokat.

## Kockázatos Fájlok

- `service/user_service.py`: admin CRUD, jelszócsere, forgot password, audit, session invalidáció és cache törlés egyben.
- `repository/persistence/user_repository.py`: soft delete, PII anonimizálás és auth táblák direkt invalidációja.
- `router/profile_router.py`: `/auth/me`, profile update, password flow és demo unsubscribe egy boundary fájlban.
- `router/admin_users_router.py`: admin CRUD, permission dependencyk, quota check és cache invalidáció.
- `tenant_hooks.py`: tenant schema migrációk minden tenant users táblájára.
- `cache/user_cache.py`: JWT light-path és cache-ből visszaépített részleges User, security mezőkkel.
- `domain/dto/user.py`: központi identity DTO, sok core és app modul használja.


## Sárközi Mihály - 2026.05.21
