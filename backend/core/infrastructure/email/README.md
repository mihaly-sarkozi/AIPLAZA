# core/infrastructure/email

Az `email` infrastruktúra modul a platform közös email küldési adaptere. SMTP-n keresztül küld 2FA, set-password, demo login és demo set-password emaileket, fejlesztői környezetben pedig SMTP hiányában maszkolt log preview-t ír.

## Fő felelősség

A modul egységes email façade-t ad auth, users, tenant signup és platform admin folyamatoknak. A címzett/feladó email címeket normalizálja és validálja, a sablonokat a `lang.email_templates` rétegből tölti, majd production módban TLS SMTP kapcsolatot használ.

## Fájlok

- `__init__.py`: lazy export az `EmailService` és `mask_email_body_for_log` felé.
- `email_service.py`: SMTP küldés, dev email simulation log, token/body maszkolás és sablonküldő helper metódusok.

## Kapcsolódás a nagy egészhez

A bootstrap réteg `EmailService` példányt köt az app containerbe. Az auth 2FA, users invite/forgot-password, tenant demo signup és platform admin set-password/login alert folyamatok ezt a közös service-t használják. A service strukturált eseményeket ír `core.email` logger névtérrel.

## Biztonsági Határ

SMTP hiányában a service nem dob hibát, hanem sikeres szimulált küldést logol. A logolt body preview `mask_email_body_for_log` segítségével maszkolja a 2FA kódokat, hosszú tokeneket és `token=` URL paramétereket, hogy fejlesztői logba ne kerüljön érzékeny belépési adat.

## Infrastruktúra Jelleg

Ez core infrastruktúra komponens. Nem tartalmaz auth vagy users üzleti döntést, csak közös email transport, sablonküldési façade és biztonságos dev logging felelősséget.

## Sárközi Mihály - 2026.05.21
