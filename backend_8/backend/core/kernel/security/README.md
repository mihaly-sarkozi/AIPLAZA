# core/kernel/security

A `security` könyvtár a kernel technikai és induláskori biztonsági infrastruktúrája. Ide tartoznak a HTTP edge védelmek, CSRF/cookie/rate limit helperök, security headerek, permission service és azok a startup guardok, amelyek hibás vagy veszélyes konfigurációval nem engedik elindulni az alkalmazást.

## Fő felelősség

Ez a csomag framework-szintű védelmet ad. Nem itt van az auth domain flow, a token kiadás vagy session üzleti logika; azok az auth modulban maradnak. Itt azok az általános védelmi szabályok élnek, amelyek több routert, modult vagy process indulást érintenek.

## Runtime Védelem

- `cookie_policy.py`: refresh, platform-admin refresh, WebSocket és channel chat cookie beállítás/törlés szabályai.
- `csrf.py`: double-submit CSRF token helperök.
- `csrf_middleware.py`: state-changing API kérések CSRF validációja.
- `rate_limit.py`: SlowAPI limiter, rate limit kulcsok és fallback throttle érzékeny endpointokra.
- `security_headers_middleware.py`: CSP, HSTS és alap browser security headerek.
- `permission_service.py`: manifest permissionök és role alapú jogosultság ellenőrzés.
- `prod_guard.py`: veszélyes karbantartó scriptek production futtatásának tiltása.

## Startup Guardok

- `security_startup_checks.py`: közös startup security check belépési pont.
- `startup_guards.py`: kernel technikai guard orchestrátor.
- `errors.py`: közös `SecurityConfigError`.
- `auth_policy_guards.py`: JWT issuer/audience, 2FA, password policy és invite TTL guardok.
- `jwt_guards.py`: JWT secret jelenlét, hossz és entrópia ellenőrzés.
- `cookie_guards.py`: refresh cookie Secure/SameSite policy ellenőrzés.
- `http_guards.py`: CSRF, trusted hosts és CORS/tenant domain guardok.
- `rate_limit_guards.py`: rate limit értékek és production Redis URL ellenőrzés.
- `tenant_guards.py`: demo signup, billing provider, legacy knowledge ingest és PII production hardening.
- `token_ttl_guards.py`: access és refresh token TTL policy ellenőrzés.

## Kapcsolódás a nagy egészhez

Az `http/middleware_registration.py` köti be a CSRF, rate limit fallback és security header middleware-eket. Az `app/app_factory.py` futtatja a startup security checkeket, a runtime assembly pedig a `permission_service.py`-t építi fel a manifest permissionökből. Routerek közvetlenül használhatják a cookie, CSRF és rate limit helperöket.

# Sárközi Mihály - 2026.05.21