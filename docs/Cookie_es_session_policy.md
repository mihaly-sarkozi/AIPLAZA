# Cookie és session policy (auth, multi-tenant, subdomain)

A backend és a frontend/integráció együtt alkotja a biztonságos session kezelést. Subdomain tenancy (pl. `demo.local`, `acme.local`) miatt a cookie domain politika és az access token tárolás kritikus.

---

## Backend (refresh token cookie)

- **Refresh token** csak cookie-ban kerül kliensre; a cookie szigorúan:
  - **HttpOnly** – JavaScript nem éri el (XSS nem lopja)
  - **Secure** – élesben csak HTTPS-en küldi (config: `cookie_secure`)
  - **SameSite** – `lax` vagy `strict` (config: `cookie_samesite`); csökkenti a cross-site kéréseket
  - **Path=/api** – csak `/api` kéréseknél küldi a böngésző
- **Domain nincs beállítva** → **host-only cookie**: a cookie csak azt a hostot “tartozik”, aki beállította.  
  Tehát `demo.local`-on beállított refresh cookie **nem** megy `acme.local`-ra – **tenant aldomainről tenant aldomainre nem szivárog a session**.
- Beállítás és törlés ugyanazzal a path/secure/samesite/httponly kombinációval történik (különben a törlés nem mindig sikerül).

Implementáció: `apps/core/security/cookie_policy.py` (`set_refresh_cookie`, `clear_refresh_cookie`), `apps/auth/presentation/auth_router.py`.

---

## Frontend / integráció

### Access token

- **NE tárold localStorage-ban vagy sessionStorage-ban** – XSS esetén a script elolvashatja és továbbadhatja a tokent.
- **Csak memóriában** (pl. Zustand/React state): oldal újratöltéskor a token elvész, a session a **refresh token HttpOnly cookie** miatt tovább él; a frontend első API hívás előtt (vagy 401 után) hívja a `/auth/refresh`-t (cookie automatikusan menni fog), és az új access tokent szintén csak memóriában tartja.

### Refresh token

- A refresh tokent **csak a backend állítja be** HttpOnly cookie-ként; a kliens **nem olvassa, nem írja**.
- API hívásoknál **withCredentials: true** (axios) / `credentials: 'include'` (fetch), hogy a böngésző mindig elküldje a cookie-t a backendnek (same-origin vagy a CORS allow-credentials konfig szerint).

### Subdomain / tenancy

- Minden tenant saját subdomain (pl. `demo.local`, `acme.local`). A cookie **host-only** (nincs `domain`), ezért:
  - `demo.local` sessionje **nem** látszik `acme.local`-on,
  - tenant aldomainről tenant aldomainre **nem szivárog** a session.
- Ha valahol saját domainet állítasz cookie-hoz, **ne** használj széles domainet (pl. `.local`), mert akkor minden subdomain megkapná a cookie-t.

### Összefoglalva

| Elem            | Követelmény |
|-----------------|------------|
| Refresh token   | Csak HttpOnly, Secure, SameSite cookie; domain nincs (host-only). |
| Access token    | Csak memóriában; **ne** localStorage/sessionStorage. |
| API hívás       | `withCredentials: true` / `credentials: 'include'`. |
| Tenant izoláció | Host-only cookie; ne állíts széles domainet. |

---

## Konfig (backend)

- `cookie_secure`: `true` élesben (csak HTTPS).
- `cookie_samesite`: `lax` (alap) vagy `strict` (még szigorúbb cross-site küldés ellen).
