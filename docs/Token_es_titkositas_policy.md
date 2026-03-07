# Titkosítás és token policy (kötelező)

Az alábbi szabályok kötelezőek: auth biztonság, token élettartam és érzékeny végpontok védelme.

---

## 1. Refresh token csak HttpOnly cookie-ban

- A **refresh token csak HttpOnly cookie-ban** kerül a kliensre; **nem** a válasz body-ban, **nem** headerben küldve.
- A kliens **nem tárolja, nem olvassa** a refresh tokent (cookie-t a böngésző kezeli; JS nem éri el → XSS nem lopja).
- Refresh kérés: **csak** a böngésző által küldött `Cookie: refresh_token=...` fogadható; **nem** fogadunk `X-Refresh-Token` header-t (akkor a token kikerülne a cookie-ból és nem „csak cookie-ban élne”).
- Részletek: [Cookie_es_session_policy.md](Cookie_es_session_policy.md).

---

## 2. Access token rövid életű

- Az **access token rövid életű** (pl. 15 perc, config: `access_ttl_min`).
- Új access token csak refresh token (cookie) felhasználásával kapható; a frontend 401 után refresh-t hív, és az új access tokent csak memóriában tartja.
- Hosszú access TTL (pl. órák) **ne** legyen: kisebb ablak, ha a token kikerül.

---

## 3. Token verify: mindig iss + aud + nbf

- **Minden** JWT ellenőrzésnél (access és refresh) kötelező:
  - **iss** (issuer): csak a mi alkalmazásunk által kiadott token fogadható (config: TokenService `issuer`, élesben kötelező).
  - **aud** (audience): opcionális de élesben ajánlott (pl. API azonosító); ha be van állítva, a verify ellenőrzi.
  - **nbf** (not before): a tokenben szerepel, a könyvtár alapból ellenőrzi.
- Rossz iss/aud/nbf → token elutasítva (InvalidTokenError).

---

## 4. Security version kötelező check érzékeny végpontokon

- **Érzékeny végpont**: minden olyan route, ahol jogosultságváltozás (role, is_active, revoke) azonnal érvénybe kell lépjen.
- Ezeken **mindig** teljes user load (DB/cache) + **user_ver / tenant_ver** egyeztetés (security version check); **nem** elég csak a token payload.
- Ha a token `user_ver` / `tenant_ver` nem egyezik a jelenlegi értékkel → 401 (force revoke).
- A light-path (token-only) auth **nem** használható érzékeny végpontokon (lásd 5.).

---

## 5. Light-path auth csak nagyon szűk, alacsony kockázatú route-okon

- **Light path**: token + allowlist ellenőrzés, **nincs** DB user load, **nincs** security version check (→ role/revoke változás csak access token lejáratakor lép életbe).
- Light path **csak** olyan, **nagyon szűk**, **alacsony kockázatú** route prefixekre engedélyezett, ahol:
  - read-only vagy minimális írás,
  - nincs érzékeny adat (pl. nincs admin-only, nincs jogosultságváltoztatás).
- Példa: **csak** `/api/chat` (beszélgetés; role változás kockázata elfogadható rövid TTL mellett). Pl. `/api/knowledge` admin-only részek miatt **nem** light path.
- Új route light path-ként való felvételéhez: szándékos döntés, alacsony kockázat dokumentálva.

---

## Implementáció (hivatkozások)

| Policy | Hol |
|--------|-----|
| Refresh csak cookie | `cookie_policy.py`, `auth_router`: set_refresh_cookie; TokenResp **nem** tartalmaz refresh_token; refresh endpoint **csak** cookie-t fogad |
| Access rövid TTL | `config/base.py`: `access_ttl_min`; `TokenService` |
| verify iss/aud/nbf | `TokenService.verify()`: issuer/audience kwargs; nbf alapból a jwt.decode-dal |
| Security version érzékeny végpontokon | `AuthMiddleware`: nem light path → _get_user + version check |
| Light path szűk / feature flag | `config/base.py`: `auth_light_paths` (vesszővel elválasztott prefixek; üres = kikapcsolva). Alap: `/api/chat`. Részletesen: `docs/Auth_light_paths.md`. Mérés: INFO log `auth_light_path`. |
