# PII teszt lefedettségi mátrix

Sorok = entitástípusok (legacy / policy név). Oszlopok = pozitív / negatív / edge case / replacement / integration.

Jelölés: ✓ = lefedve, (✓) = részleges/xfail dokumentált, — = nincs teszt.

| Entitás (legacy) | positive | negative | edge_case | replacement | integration |
|------------------|----------|----------|-----------|-------------|-------------|
| email | ✓ | — | ✓ (több formátum) | ✓ | ✓ |
| telefonszám | ✓ | — | ✓ (HU, ES, 06) | ✓ | ✓ |
| név | ✓ | — | — | ✓ | ✓ |
| dátum / születési dátum | ✓ | — | ✓ (év.hónap.nap, szóköz) | — | ✓ |
| cím | ✓ | — | — | — | ✓ |
| iban | ✓ | — | ✓ (szóköz nélkül) | — | ✓ |
| rendszám | ✓ | — | ✓ (ABC-123, AB 12 CD 34) | — | ✓ |
| ügyfélazonosító | ✓ | — | ✓ (UGY-, CLIENT-, #) | — | ✓ |
| ticket_id | ✓ | — | — | — | ✓ |
| szerződésszám | ✓ | — | — | — | ✓ |
| bankszámla | — | — | — | — | — |
| kártyaszám | (✓) xfail | — | — | — | (✓) |
| vin | ✓ | — | ✓ (VIN: prefix) | — | ✓ |
| imei | ✓ | — | ✓ (IMEI: prefix) | — | ✓ |
| mac_cím | ✓ | — | — | — | ✓ |
| motorszám / alvázszám | ✓ | — | — | — | unit |
| ip_cím | (✓) xfail | — | — | — | (✓) |
| session_id | — | — | — | — | — |
| device_id | — | — | — | — | — |
| munkavállalói_azonosító | — | — | — | — | — |
| személyi_azonosító / TAJ | (✓) xfail | — | — | — | (✓) |
| adóazonosító | (✓) xfail | — | — | — | (✓) |
| útlevél | — | — | — | — | — |
| jogosítvány | — | — | — | — | — |
| szervezet | ✓ policy | — | — | — | ✓ (policy) |
| hely | ✓ policy | — | — | — | ✓ (policy) |
| felhasználónév / becenév | (✓) xfail | — | — | — | (✓) |
| GPS koordináta | (✓) xfail | — | — | — | (✓) |

## Teszt besorolás (markerek)

- **must_pass**: valódi viselkedés teszt; sikeresen kell lefutnia. Pl. `test_vin_imei_mac_detektalva_legacy_adapteren_keresztul`, policy/replacement tesztek, unit detektor tesztek.
- **smoke_only**: csak triviális ellenőrzés (pl. válasz lista, 200). Pl. `test_get_kb_user_returns_200_filtered_list`, `test_list_users_success_returns_list` – kiegészítve valódi assertekkel (elemek struktúrája).
- **expected_fail_not_implemented**: funkció még nincs (vagy korlátozottan van) implementálva; `@pytest.mark.xfail(reason="...")`. Pl. becenév, TAJ/ado, kártya, IP, GPS.

## Futtatás

```bash
# Csak valódi viselkedés tesztek (xfail/smoke kihagyása)
pytest -m must_pass

# Csak dokumentációs (xfail) tesztek
pytest -m expected_fail_not_implemented

# Smoke tesztek
pytest -m smoke_only
```
