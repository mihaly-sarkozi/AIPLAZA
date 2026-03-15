# apps/knowledge/pii/sanitization.py
"""
Standardized placeholders, generalization mode, and robust replacement.
- Placeholders: [EMAIL_ADDRESS], [PHONE_NUMBER], [PERSON_NAME], etc.
- Generalization: exact person name → "contact person", date → "specific date", address → "postal address".
- Deduplication: longer matches win when overlaps (name inside email, address inside location).
- Replacement from end to start so offsets do not corrupt.
"""
from __future__ import annotations

from typing import List, Tuple

# PiiMatch = (start, end, data_type: str, value: str)

# Legacy type (név, email, …) → standard placeholder tag
LEGACY_TO_STANDARD_PLACEHOLDER: dict[str, str] = {
    "név": "[PERSON_NAME]",
    "email": "[EMAIL_ADDRESS]",
    "telefonszám": "[PHONE_NUMBER]",
    "cím": "[POSTAL_ADDRESS]",
    "dátum": "[DATE]",
    "születési_dátum": "[DATE_OF_BIRTH]",
    "iban": "[IBAN]",
    "bankszámla": "[BANK_ACCOUNT_NUMBER]",
    "kártyaszám": "[PAYMENT_CARD_NUMBER]",
    "rendszám": "[VEHICLE_REGISTRATION]",
    "vin": "[VIN]",
    "motorszám": "[ENGINE_IDENTIFIER]",
    "alvázszám": "[CHASSIS_IDENTIFIER]",
    "ügyfélazonosító": "[CUSTOMER_ID]",
    "szerződésszám": "[CONTRACT_NUMBER]",
    "ticket_id": "[TICKET_ID]",
    "munkavállalói_azonosító": "[EMPLOYEE_ID]",
    "ip_cím": "[IP_ADDRESS]",
    "mac_cím": "[MAC_ADDRESS]",
    "imei": "[IMEI]",
    "device_id": "[DEVICE_ID]",
    "session_id": "[SESSION_ID]",
    "személyi_azonosító": "[PERSONAL_ID]",
    "adóazonosító": "[TAX_ID]",
    "útlevél": "[PASSPORT_NUMBER]",
    "jogosítvány": "[DRIVER_LICENSE_NUMBER]",
    "health_hint": "[HEALTH_DATA_HINT]",
    "biometric_hint": "[BIOMETRIC_HINT]",
    "political_hint": "[POLITICAL_OPINION_HINT]",
    "religion_hint": "[RELIGION_HINT]",
    "union_hint": "[UNION_MEMBERSHIP_HINT]",
    "sexual_orientation_hint": "[SEXUAL_ORIENTATION_HINT]",
    "user_id": "[USER_ID]",
    "cookie_id": "[COOKIE_ID]",
}

# Generalization: legacy type → human-readable generic label (no PII)
LEGACY_TO_GENERALIZATION: dict[str, str] = {
    "név": "contact person",
    "email": "[email]",
    "telefonszám": "[phone]",
    "cím": "postal address",
    "dátum": "specific date",
    "születési_dátum": "date of birth",
    "iban": "[iban]",
    "bankszámla": "[bank account]",
    "kártyaszám": "[payment card]",
    "rendszám": "[vehicle registration]",
    "vin": "[vin]",
    "motorszám": "[engine identifier]",
    "alvázszám": "[chassis identifier]",
    "ügyfélazonosító": "[customer id]",
    "szerződésszám": "[contract number]",
    "ticket_id": "[ticket id]",
    "munkavállalói_azonosító": "[employee id]",
    "ip_cím": "[ip address]",
    "mac_cím": "[mac address]",
    "imei": "[imei]",
    "device_id": "[device id]",
    "session_id": "[session id]",
    "személyi_azonosító": "[personal id]",
    "adóazonosító": "[tax id]",
    "útlevél": "[passport]",
    "jogosítvány": "[driver license]",
    "user_id": "[user id]",
    "cookie_id": "[cookie id]",
}

DEFAULT_PLACEHOLDER = "[PII]"
DEFAULT_GENERALIZATION = "[redacted]"


def _standard_placeholder(legacy_type: str) -> str:
    return LEGACY_TO_STANDARD_PLACEHOLDER.get(
        (legacy_type or "").strip().lower(), DEFAULT_PLACEHOLDER
    )


def _generalization_text(legacy_type: str) -> str:
    return LEGACY_TO_GENERALIZATION.get(
        (legacy_type or "").strip().lower(), DEFAULT_GENERALIZATION
    )


def deduplicate_matches_longer_wins(
    matches: List[Tuple[int, int, str, str]],
) -> List[Tuple[int, int, str, str]]:
    """
    Deduplicate overlapping detections: longer span wins.
    E.g. name inside email → keep email; address inside larger location → keep longer.
    Returns matches sorted by start (for stable replacement order).
    """
    if not matches:
        return []
    # Sort by length descending, then by start ascending
    by_len = sorted(
        matches,
        key=lambda m: (-(m[1] - m[0]), m[0]),
    )
    kept: List[Tuple[int, int, str, str]] = []
    for start, end, dtype, val in by_len:
        if any(s < end and e > start for s, e, _, _ in kept):
            continue
        kept.append((start, end, dtype, val))
    return sorted(kept, key=lambda m: m[0])


def _placeholder_with_ref(legacy_type: str, ref_id: str) -> str:
    """Placeholder ref_id-val: [TYPE_ref_id], így később elővehető az eredeti érték."""
    base = LEGACY_TO_STANDARD_PLACEHOLDER.get(
        (legacy_type or "").strip().lower(), DEFAULT_PLACEHOLDER
    )
    if ref_id:
        return base.rstrip("]") + "_" + ref_id + "]"
    return base


def apply_pii_replacements(
    text: str,
    matches: List[Tuple[int, int, str, str]],
    ref_id_by_index: List[str],
    mode: str = "mask",
) -> str:
    """
    Replace PII spans with standardized placeholders (mask) or generalization text.
    Replaces from end to start so character offsets remain valid.
    Ha ref_id_by_index[i] megadott és mode=mask: [TYPE_ref_id] formátum, így az
    eredeti érték a reference_id alapján elővehető.
    """
    if not text:
        return text
    if not matches:
        return text
    if len(ref_id_by_index) != len(matches):
        ref_id_by_index = [""] * len(matches)

    def replacement_for(i: int) -> str:
        start, end, dtype, _ = matches[i]
        if mode == "generalize":
            return _generalization_text(dtype)
        if mode == "remove" or mode == "dots":
            return "..."
        ref_id = ref_id_by_index[i] if i < len(ref_id_by_index) else ""
        return _placeholder_with_ref(dtype, ref_id)

    # Build (start, end, replacement) and sort by start descending → replace from end
    repl_list = [
        (matches[i][0], matches[i][1], replacement_for(i))
        for i in range(len(matches))
    ]
    repl_list.sort(key=lambda x: -x[0])
    result = text
    for start, end, replacement in repl_list:
        result = result[:start] + replacement + result[end:]
    return result


def apply_pii_replacements_with_decisions(
    text: str,
    matches: List[Tuple[int, int, str, str]],
    decisions: List[str],
    ref_id_by_index: List[str] | None = None,
) -> tuple[str, List[int]]:
    """
    Soronkénti döntések alapján cserél.
    decisions[i] = "delete"|"mask"|"keep"
    - delete: placeholder ref_id-val (ha van), különben "..."; tároljuk personal_data-ban
    - mask: placeholder ref_id-val; tároljuk personal_data-ban
    - keep: eredeti érték marad
    ref_id_by_index: ha megadott, a mask és delete helyettesítés [TYPE_ref_id] formátumot kap.
    Vissza: (result_text, store_indices) - store_indices = mask és delete indexek (personal_data-ba kell tenni)
    """
    if not text or not matches:
        return text, []
    if len(decisions) != len(matches):
        decisions = ["mask"] * len(matches)  # fallback
    ref_id_by_index = ref_id_by_index or [""] * len(matches)
    if len(ref_id_by_index) != len(matches):
        ref_id_by_index = [""] * len(matches)

    def replacement_for(i: int) -> str:
        start, end, dtype, val = matches[i][0], matches[i][1], matches[i][2], matches[i][3]
        d = (decisions[i] or "mask").lower()
        if d == "keep":
            return val
        if d == "delete":
            ref_id = ref_id_by_index[i] if i < len(ref_id_by_index) else ""
            return _placeholder_with_ref(dtype, ref_id) if ref_id else "..."
        # mask
        ref_id = ref_id_by_index[i] if i < len(ref_id_by_index) else ""
        return _placeholder_with_ref(dtype, ref_id) if ref_id else _standard_placeholder(dtype)

    store_indices: List[int] = []
    for i in range(len(matches)):
        d = (decisions[i] or "mask").lower()
        if d in ("mask", "delete"):
            store_indices.append(i)

    repl_list = [
        (matches[i][0], matches[i][1], replacement_for(i))
        for i in range(len(matches))
    ]
    repl_list.sort(key=lambda x: -x[0])
    result = text
    for start, end, replacement in repl_list:
        result = result[:start] + replacement + result[end:]
    return result, store_indices
