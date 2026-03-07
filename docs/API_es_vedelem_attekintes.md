# API útvonalak és védelem – áttekintés

Ez a doc a `main.py` után következő rétegeket írja le: **milyen API végpontok vannak** és **hogyan védik őket** (CORS, auth, rate limit, security headers).

---

## 1. API útvonalak (routerek)

Minden végpont a **`/api`** prefix alatt van. A routerek és a végpontok:

### 1.1 Auth router (`apps/auth/presentation/auth_router.py`)

| Metódus | Útvonal | Rate limit | Auth | Mit csinál |
|--------|---------|------------|------|------------|
| POST   | `/api/auth/login`   | 5/perc | nem | Bejelentkezés; 2FA esetén `TwoFactorRequiredResp`; siker esetén refresh cookie + access token + user |
| POST   | `/api/auth/refresh` | 5/perc | nem | Cookie-ból refresh token → új access + új refresh cookie |
| POST   | `/api/auth/logout`  | 10/perc | nem | Refresh token érvénytelenítés + cookie törlése |
| GET    | `/api/auth/me`      | –     | **igen** (`get_current_user`) | Aktuális user (id, email, role, is_superuser) |

- **Védelem:** Login/refresh/logout nyilvános; `/auth/me` csak bejelentkezett usernek (JWT kell).

### 1.2 User router (`apps/auth/presentation/user_router.py`)

| Metódus | Útvonal | Rate limit | Auth | Mit csinál |
|--------|---------|------------|------|------------|
| GET    | `/api/users`        | 30/perc | **superuser** | Összes user listázása |
| GET    | `/api/users/{user_id}` | –   | **superuser** | Egy user lekérése |
| POST   | `/api/users`        | 10/perc | **superuser** | Új user létrehozása |
| PUT    | `/api/users/{user_id}` | 20/perc | **superuser** | User frissítése |
| DELETE | `/api/users/{user_id}` | 10/perc | **superuser** | User törlése |

- **Védelem:** Minden végpont `get_current_superuser` → előbb `get_current_user` (JWT), majd `is_superuser` ellenőrzés.

### 1.3 Settings router (`apps/auth/presentation/settings_router.py`)

| Metódus | Útvonal | Rate limit | Auth | Mit csinál |
|--------|---------|------------|------|------------|
| GET    | `/api/settings` | – | **admin** | Beállítások (pl. two_factor_enabled; 2FA mindig be van kapcsolva, nincs kapcsoló) |

- **Védelem:** `get_current_admin` → `get_current_user` + `role == "admin"`.

### 1.4 Chat router (`apps/chat/presentation/chat_router.py`)

| Metódus | Útvonal | Rate limit | Auth | Mit csinál |
|--------|---------|------------|------|------------|
| POST   | `/api/chat` | 30/perc | (nincs explicit Depends) | Kérdés → válasz (chat service) |

- **Védelem:** A route nem hív `get_current_user`-t; ha kell auth, később hozzá lehet adni. Rate limit: 30/perc.

### 1.5 Knowledge router (`apps/knowledge/presentation/knowledge_router.py`)

| Metódus | Útvonal | Rate limit | Auth | Mit csinál |
|--------|---------|------------|------|------------|
| GET    | `/api/kb`                 | –   | **admin** | Összes KB listázása |
| POST   | `/api/kb`                 | 5/perc | **admin** | Új KB létrehozása |
| PUT    | `/api/kb/{uuid}`          | –   | **admin** | KB módosítása |
| DELETE | `/api/kb/{uuid}`          | –   | **admin** | KB törlése |
| POST   | `/api/kb/{uuid}/train`    | –   | (nincs) | Nyers szöveg betanítása |
| POST   | `/api/kb/{uuid}/train/text`  | – | (nincs) | Szöveg betanítása (alias) |
| POST   | `/api/kb/{uuid}/train/file`  | – | (nincs) | Fájl feltöltés + betanítás |

- **Védelem:** List/create/update/delete **admin** (`get_current_user_admin`). A `/train` végpontok jelenleg **nem** használják a `get_current_user_admin`-t (figyelj rá, ha élesben csak adminnak szabad).

---

## 2. Védelem – rétegek és sorrend

Egy kérés a következő sorrendben éri el a route-ot (middleware-ek alulról felfelé futnak a requestnél):

### 2.1 CORS (main.py)

- **Mit csinál:** Megmondja a böngészőnek: mely origin(ok) hívhatják az API-t (`localhost:5173`), engedélyezett a cookie (credentials), és az `Authorization`, `Content-Type` fejlécek.
- **Miért:** Cross-origin hívások (frontend más portról) nélküle blokkolná a böngésző.

### 2.2 Auth middleware (`apps/core/middleware/auth_middleware.py`)

- **Mit csinál:**
  - OPTIONS kérést továbbadja auth nélkül (CORS preflight).
  - Egyéb kéréseknél kiolvassa az `Authorization: Bearer <token>` fejlécet.
  - Ha van token, a `TokenService.verify(token)` dekódolja a JWT-t; az eredmény a `request.state.user_token_payload`-ba kerül (pl. `sub`, `typ`).
  - Ha nincs token vagy invalid → `request.state.user_token_payload = None`.
- **Miért:** Egy helyen történik a token ellenőrzés; a route-ok nem dekódolnak JWT-t, csak a `auth_dependencies`-ben a payload alapján döntünk (401 / user betöltése).

### 2.3 Auth dependencies (`apps/core/security/auth_dependencies.py`)

A route-ok ezeket használják, ha bejelentkezett usert várnak:

- **`get_current_user_id(request)`**  
  - `request.state.user_token_payload`-ból veszi a user id-t (`sub`).  
  - Ha nincs payload vagy `typ != "access"` → 401.

- **`get_current_user`**  
  - `get_current_user_id` + LoginService → user betöltése ID alapján.  
  - Nincs user → 401.

- **`get_current_user_admin`**  
  - `get_current_user` + `user.role == "admin"` ellenőrzés.  
  - Nem admin → 403.

A user_router és settings_router további szűrőket használnak:

- **`get_current_superuser`** (user_router): `get_current_user` + `user.is_superuser`.
- **`get_current_admin`** (settings_router): `get_current_user` + `user.role == "admin"`.

### 2.4 Rate limiting (slowapi)

- **Hol:** `apps/core/middleware/rate_limit_middleware.py` – egy `Limiter` példány, `key_func` = user vagy IP (a `request.state` alapján).
- **Hol használják:** `main.py`: `app.state.limiter = limiter`; a route-ok a `@limiter.limit("X/minute")` dekorátorral korlátozzák a kérést.
- **Túllépés:** `RateLimitExceeded` → `main.py`-beli handler → 429 + magyar üzenet.

### 2.5 Security headers (main.py – SecurityHeadersMiddleware)

- **Mit csinál:** Minden válaszhoz hozzáadja: X-Frame-Options, X-Content-Type-Options, X-XSS-Protection, Referrer-Policy, Content-Security-Policy (frame-ancestors).
- **Miért:** Clickjacking, MIME-sniffing, XSS kockázat csökkentése.

---

## 3. Összefoglaló – „kérés útja”

1. **Kérés érkezik** → CORS middleware (ha preflight, válasz; különben tovább).
2. **Auth middleware** → JWT kiolvasása, ellenőrzés, `request.state.user_token_payload` beállítása.
3. **Rate limit** → a konkrét route `@limiter.limit(...)` ellenőrzi; túllépés → 429.
4. **Security headers** → válaszhoz fejlécek.
5. **Route** → ha védett, a `Depends(get_current_user)` vagy admin/superuser dependency 401/403-at dob, ha nincs jogosultság; különben a handler fut.

Így az **útvonal** (melyik route fut) és a **védelem** (CORS, JWT, role/superuser, rate limit, headers) együtt adja az API viselkedését.
