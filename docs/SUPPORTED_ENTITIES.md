# Támogatott PII entitástípusok

A **egyetlen hivatalos forrás** az `apps.knowledge.pii.entities` modul:
- **IMPLEMENTED_LEGACY_NAMES** = a policy által kezelt és a pipeline (pii_gdpr + NER) által detektált típusok.
- **WEAK_ENTITIES / MEDIUM_ENTITIES / STRONG_ENTITIES** = erősség szerinti halmazok (policy és adapter ezeket használja).

Új típus hozzáadása: előbb frissítsd az `entities.py`-t, majd ezt a dokumentumot.

## Implementált típusok (IMPLEMENTED_LEGACY_NAMES)

| Belső név (legacy) | weak | medium | strong | Detektor / megjegyzés |
|---------------------|------|--------|--------|------------------------|
| `email` | ✓ | ✓ | ✓ | RegexDetector, EmailClassifier |
| `telefonszám` | ✓ | ✓ | ✓ | RegexDetector |
| `iban` | — | ✓ | ✓ | RegexDetector |
| `rendszám` | — | ✓ | ✓ | RegexDetector, VehicleDetector |
| `ügyfélazonosító` | — | ✓ | ✓ | RegexDetector |
| `szerződésszám` | — | ✓ | ✓ | RegexDetector |
| `ticket_id` | — | ✓ | ✓ | RegexDetector |
| `dátum` | — | ✓ | ✓ | RegexDetector (DATE), NERDetector (DATE) – általános dátum |
| `születési_dátum` | — | ✓ | ✓ | RegexDetector (DATE_OF_BIRTH) – Született:/dob/date of birth kontextus |
| `név` | — | ✓ | ✓ | NERDetector (PERSON/PER) |
| `cím` | — | ✓ | ✓ | RegexDetector (POSTAL_ADDRESS) |
| `vin` | — | ✓ | ✓ | VINRecognizer, RegexDetector, VehicleDetector |
| `imei` | — | ✓ | ✓ | IMEIRecognizer, TechnicalIdentifierDetector |
| `mac_cím` | — | ✓ | ✓ | MACRecognizer, RegexDetector |
| `ip_cím` | — | ✓ | ✓ | IPRecognizer, RegexDetector |
| `motorszám` | — | ✓ | ✓ | EngineIdRecognizer, VehicleDetector |
| `alvázszám` | — | ✓ | ✓ | EngineIdRecognizer (chassis), VehicleDetector |
| `bankszámla` | — | ✓ | ✓ | BankAccountRecognizer, RegexDetector |
| `kártyaszám` | — | ✓ | ✓ | RegexDetector (PAYMENT_CARD_NUMBER) |
| `személyi_azonosító` | — | ✓ | ✓ | DocumentIdentifiersRecognizer, RegexDetector (TAJ formátum) |
| `adóazonosító` | — | ✓ | ✓ | DocumentIdentifiersRecognizer, RegexDetector |
| `útlevél` | — | ✓ | ✓ | DocumentIdentifiersRecognizer, RegexDetector |
| `jogosítvány` | — | ✓ | ✓ | DocumentIdentifiersRecognizer, RegexDetector |
| `munkavállalói_azonosító` | — | ✓ | ✓ | RegexDetector (EMPLOYEE_ID) |
| `device_id` | — | ✓ | ✓ | RegexDetector, TechnicalIdentifierDetector |
| `session_id` | — | ✓ | ✓ | RegexDetector, TechnicalIdentifierDetector |
| `szervezet` | — | — | ✓ | NERDetector (ORG/ORGANIZATION) |
| `hely` | — | — | ✓ | NERDetector (GPE/LOC/LOCATION) |

## Erősség (sensitivity)

- **weak**: csak `email`, `telefonszám`.
- **medium**: weak + IBAN, rendszám, dátum, születési_dátum, ügyfél/szerz/ticket, név, cím, bankszámla, kártyaszám, VIN, motorszám, alvázszám, IP, MAC, IMEI, session_id, device_id, munkavállalói, személyi/adó/útlevél/jogosítvány.
- **strong**: medium + `szervezet`, `hely`.

## Nem (még) implementált (NOT_YET_LEGACY_NAMES)

- `felhasználónév`, `becenév`, `gps` — backlog; xfail tesztek / NOT_YET_SUPPORTED.md.

## Programozott használat

```python
from apps.knowledge.pii.entities import (
    IMPLEMENTED_LEGACY_NAMES,
    SUPPORTED_LEGACY_NAMES,  # alias
    WEAK_ENTITIES,
    MEDIUM_ENTITIES,
    STRONG_ENTITIES,
)
```

A policy (`entities_for_sensitivity`) és az adapter a fenti halmazokat használja; a sanitizer placeholder kulcsait az `entities.py` és az adapter típusneveivel konzisztensen tartja.
