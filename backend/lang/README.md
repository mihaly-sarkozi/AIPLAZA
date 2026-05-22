# lang

A `lang` csomag a backend user-facing lokalizációs contract rétege. API hibaüzeneteket és email sablonokat ad több nyelven, jelenleg `hu`, `en` és `es` nyelvkódokra.

## Fő felelősség

A modul célja, hogy a backend service-ek ne hardcoded szövegeket küldjenek emailben vagy API detail üzenetként. Az üzenetek hibakódhoz, az email sablonok template azonosítóhoz kötődnek, a hiányzó vagy nem támogatott nyelv pedig a default magyar (`hu`) készletre esik vissza.

## Fájlok

- `__init__.py`: egységes exportfelület `get_email_template`, `get_message`, `ErrorCode` és `DEFAULT_LANG` számára.
- `messages.py`: `ErrorCode` enum, `lang_from_request()` Accept-Language normalizálás és hu/en/es API üzenetek.
- `email_templates.py`: hu/en/es email sablonok 2FA, set-password, demo login és demo set-password folyamatokhoz.

## Kapcsolódás a nagy egészhez

Az `EmailService` a `get_email_template()` és `get_2fa_token_block()` helperen keresztül tölti be a lokalizált email szövegeket. Az auth és user-facing routerek a `get_message()` helperrel adhatnak vissza hibakódhoz tartozó lokalizált szöveget. A tenant és user profil policyk már `hu/en/es` locale készletet támogatnak, ezért az email és API message készletnek is együtt kell tartania ezt a három nyelvet.

## Bővítési Szabály

Új nyelv hozzáadásakor mindkét készletet bővíteni kell: `messages.py` alatt minden `ErrorCode` kapjon fordítást, `email_templates.py` alatt pedig minden template kulcs ugyanazokkal a placeholderekkel jelenjen meg. Új email template hozzáadásakor minden támogatott nyelvben legyen `subject` és `body`.

## Core/Framework Jelleg

Ez shared backend lokalizációs réteg. Nem üzleti modul, hanem közös text contract, amelyet auth, users, tenant signup és email infrastruktúra használ.

## Sárközi Mihály - 2026.05.21
