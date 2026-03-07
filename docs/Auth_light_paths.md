# Auth light path – dokumentáció és mérés

## Mi az a light path?

A **light path** azokra a path prefixekre vonatkozik, ahol az auth middleware **nem** tölti be a usert a DB-ből és **nem** ellenőrzi a security versiont (user_ver / tenant_ver). Ehelyett csak a JWT payload + allowlist alapján egy minimál user (id, role, is_active=True) kerül `request.state.user`-be. Ez gyorsabb (nincs DB/cache round-trip), de kompromisszum:

- **Előny:** Alacsonyabb késleltetés, kevesebb DB terhelés az adott route-okon.
- **Kockázat:** Ha közben megváltozik a user role vagy is_active (revoke), az **csak az access token lejáratakor** lép életbe; addig a light path route továbbra is a régi role-t látja a tokenból.

Ezért a light path **csak alacsony kockázatú** végpontokra ajánlott.

---

## Jelenlegi beállítás

- **Alapértelmezett:** egyetlen prefix: **`/api/chat`**. Ez vállalható kompromisszum: a chat végpont nem érzékeny a role/revoke azonnali megjelenésére (a következő token refresh vagy access lejárat már friss adatot ad).
- **Érzékeny route-ok** (pl. `/api/knowledge`, `/api/users`, admin műveletek) **nincsenek** a light path-on: ezeken mindig teljes user load + version check történik.

---

## Konfiguráció (feature flag)

A light path listája konfigból jön; így szűkíthető vagy teljesen kikapcsolható.

| Környezet | Konfig | Jelentés |
|-----------|--------|----------|
| Config mező | `auth_light_paths` (config/base.py) | Vesszővel elválasztott path prefixek. Üres string = **light path kikapcsolva** (mindig teljes user load). |
| .env | `AUTH_LIGHT_PATHS` | Pl. `AUTH_LIGHT_PATHS=/api/chat` vagy `AUTH_LIGHT_PATHS=` (üres = disable). |

Példák:

- `AUTH_LIGHT_PATHS=/api/chat` – csak chat (alapértelmezett).
- `AUTH_LIGHT_PATHS=` vagy `AUTH_LIGHT_PATHS=""` – light path **kikapcsolva**, minden route teljes auth.
- `AUTH_LIGHT_PATHS=/api/chat,/api/status` – két prefix (a második példa; csak ha van ilyen alacsony kockázatú route).

---

## Mérés

A light path használata **explicit logolva** van, hogy monitorozható legyen:

- **Hol:** `apps/core/middleware/auth_middleware.py`
- **Mikor:** Ha egy kérés a light path prefix alá esik és a token + allowlist érvényes, a middleware `state["auth_light"] = True` mellett egy **INFO** szintű log bejegyzés készül:
  - `auth_light_path` üzenet
  - Extra mezők: `path`, `user_id`, `correlation_id`

Így a log aggregátorban (pl. ELK, Grafana Loki) szűrhető / aggregálható a light path használat (hány kérés ment light path-on, mely path-ok, user_id-k). Élesben érdemes ezt figyelni, hogy a kompromisszum elfogadható maradjon.

---

## Összefoglaló

| Cél | Megvalósítás |
|-----|--------------|
| Light path szűk / kikapcsolható | `auth_light_paths` config; alap: csak `/api/chat`; üres = disable |
| Explicit dokumentáció | Ez a fájl (docs/Auth_light_paths.md) |
| Mérés | INFO log `auth_light_path` + path, user_id, correlation_id |

A token és titkosítás policy összesen: `docs/Token_es_titkositas_policy.md`.
