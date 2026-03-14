# Entitás → policy térkép (sensitivity, default action, placeholder)

A dedikált recognizerek (IP, MAC, IMEI, VIN, engine/chassis, bank account, document IDs) a **medium** és **strong** erősségnél maszkolásra kerülnek. Alapértelmezett action: **MASK** (policy engine balanced/strict módban).

| Entitás (EntityType) | RiskClass | weak | medium | strong | Default action | Placeholder |
|----------------------|-----------|------|--------|--------|----------------|-------------|
| IP_ADDRESS | INDIRECT_IDENTIFIER | — | ✓ | ✓ | MASK | [IP_ADDRESS] |
| MAC_ADDRESS | INDIRECT_IDENTIFIER | — | ✓ | ✓ | MASK | [MAC_ADDRESS] |
| IMEI | INDIRECT_IDENTIFIER | — | ✓ | ✓ | MASK / REVIEW | [IMEI] |
| VIN | INDIRECT_IDENTIFIER | — | ✓ | ✓ | MASK | [VIN] |
| ENGINE_IDENTIFIER | INDIRECT_IDENTIFIER | — | ✓ | ✓ | MASK | [ENGINE_IDENTIFIER] |
| CHASSIS_IDENTIFIER | INDIRECT_IDENTIFIER | — | ✓ | ✓ | MASK | [CHASSIS_IDENTIFIER] |
| BANK_ACCOUNT_NUMBER | DIRECT_PII | — | ✓ | ✓ | MASK | [BANK_ACCOUNT_NUMBER] |
| PERSONAL_ID (TAJ) | DIRECT_PII | — | ✓ | ✓ | MASK | [PERSONAL_ID] |
| TAX_ID | DIRECT_PII | — | ✓ | ✓ | MASK | [TAX_ID] |
| PASSPORT_NUMBER | DIRECT_PII | — | ✓ | ✓ | MASK | [PASSPORT_NUMBER] |
| DRIVER_LICENSE_NUMBER | DIRECT_PII | — | ✓ | ✓ | MASK | [DRIVER_LICENSE_NUMBER] |

A legacy policy (`apps/knowledge/pii/policy.py`) MEDIUM_ENTITIES és STRONG_ENTITIES halmaza tartalmazza a fenti típusok legacy neveit (ip_cím, mac_cím, imei, vin, motorszám, alvázszám, bankszámla, személyi_azonosító, adóazonosító, útlevél, jogosítvány). A policy engine (`apps/knowledge/pii_gdpr/policy/policy_engine.py`) _DEFAULT_ENTITY_RISK és a Sanitizer MASK_PLACEHOLDERS ezzel konzisztens.
