# shared/utils

A `shared/utils` csomag általános, modulfuggetlen backend helper réteg. Olyan kisméretű utility funkciókat tartalmaz, amelyeket core, infrastructure és app modulok is biztonságosan használhatnak domain- vagy perzisztenciafüggés nélkül.

## Fő felelősség

Ez a réteg közös időkezelést, UTC datetime normalizálást, SHA-256 hash-elést, log/audit payload sanitizationt és slug normalizálást-validációt ad. A cél nem egy vegyes "mindenes" könyvtár, hanem stabil, alacsony szintű helper contractok gyűjteménye.

## Fájlok

- `__init__.py`: publikus exportfelület a közös utility függvényekhez és osztályokhoz.
- `clock.py`: `Clock` protokoll, `SystemClock`, default clock kezelés, `utc_now()`, `utc_today()` és `utc_now_naive()` helper.
- `datetime_utils.py`: naive datetime értékek UTC-aware formára normalizálása.
- `hash.py`: `sha256_hex()` helper determinisztikus SHA-256 hex digesthez.
- `sanitization.py`: érzékeny log/audit mezők rekurzív maszkolása jelszó, token, secret, auth, email és 2FA minták alapján.
- `slug.py`: slug normalizálás és validáció tenant- és URL-barát azonosítókhoz.

## Kapcsolódás a nagy egészhez

A core observability, logging és audit rétegek a sanitization helpert használják biztonságos payload íráshoz. Auth, users és tenant repositoryk a datetime normalizálást hívják. Billing és chat időkezeléshez használja a clock helper API-t, a tenant signup és router validáció pedig a slug segédeket.

## Boundary Értékelés

A shared hely indokolt, mert a modul nem függ adatbázistól, tenant contexttől, FastAPI-tól vagy üzleti domain modellektől. Új elem csak akkor kerüljön ide, ha több modul számára hasznos, stabil, alacsony szintű helper; app-specifikus validáció, domain szabály vagy framework assembly maradjon a saját moduljában.

## Sárközi Mihály - 2026.05.21
