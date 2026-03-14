# Nem (még) támogatott / részleges entitások

**Egységes forrás:** `apps.knowledge.pii_gdpr.entity_registry` és `docs/ENTITY_REGISTRY.md`.

Minden entitás a registry-ben **IMPLEMENTED**, **PARTIALLY_IMPLEMENTED** vagy **NOT_IMPLEMENTED**. A policy, sanitizer, adapter és tesztek ezzel egyeztetnek.

## NOT_IMPLEMENTED (nincs detektor)

- **USER_ID**, **COOKIE_ID**: csak enum/sanitizer placeholder; nincs detektor.
- **Backlog** (nincs EntityType): felhasználónév, becenév, GPS – dokumentálva; xfail tesztek.

## PARTIALLY_IMPLEMENTED (korlátozott / kétértelmű)

- **POSTAL_ADDRESS** (cím): regex HU/ES; NER LOC kiegészítheti.
- **PERSONAL_ID**, **TAX_ID**, **PASSPORT_NUMBER**, **DRIVER_LICENSE_NUMBER**: ország-/formátumfüggő vagy kontextus kell.
- **DEVICE_ID**, **SESSION_ID**: regex/technical detector; metaadat jelleg.
- **Sensitive hints** (health, biometric, political, religion, union, sexual_orientation): csak kontextus/kulcsszó; nincs strukturált detektor.

## IMPLEMENTED (detektor a pipeline-ban)

Lásd `ENTITY_REGISTRY.md` teljes lista. Pl. EMAIL_ADDRESS, PHONE_NUMBER, DATE, DATE_OF_BIRTH, IBAN, VIN, VEHICLE_REGISTRATION, stb.

## DATE vs DATE_OF_BIRTH

- **DATE**: általános dátum; **ne** kezeld születési dátumként.
- **DATE_OF_BIRTH**: csak kontextus esetén (pl. „Született:”, „dob:”, „date of birth”).

## Tesztek

A „még nem támogatott” vagy kétértelmű típusokra `@pytest.mark.xfail` vagy hasonló; ha egy típus IMPLEMENTED lesz, a teszt átállítható must_pass-ra.
