"""
Kontextus alapú szám-azonosító felismerő.
Ha szám (vagy szám+kötőjel/kettőspont) van a szövegben, és előtte/utána azonosítóra utaló
kulcsszó (akár egybeírva: motorszám, alvázszám, stb.), akkor szűri.
HU, EN, ES – mindhárom nyelven.
"""
from __future__ import annotations

import re
from typing import List, Optional, Tuple

from apps.knowledge.pii_gdpr.enums import EntityType, RiskClass, RecommendedAction
from apps.knowledge.pii_gdpr.models import DetectionResult
from apps.knowledge.pii_gdpr.detectors.base import BaseDetector


# Szám/azonosító minták: kötőjel vagy kettőspont között = azonosító jelleg
# Pl. DEV-998877, 123:456, PRN-4477, node-77-eu
# Összekötő számok között: szóköz, írásjel, vagy épület/út/emelet/ajtó stb.
_CONNECTOR = (
    r"(?:\s*[./\-]?\s*|[\s./\-]*(?:épület|epulet|út|ut|útja|utja|emelet|köz|koz|"
    r"kerület|kerulet|ajtó|ajto|város|varos|tér|ter|utca|building|floor|apt|"
    r"edificio|piso|puerta)\s*)"
)

_NUMBER_ID_PATTERNS = [
    # Cím: szám + összekötő (szóköz/írásjel/épület/út/emelet/ajtó) + szám (15 épület 3 ajtó 12, 15. 3/12)
    (r"\b\d+[a-z]?(?:" + _CONNECTOR + r"\d+[a-z]?(?:\s*/\s*\d+)?\.?)*\b", 0.74),
    # Alfanumerikus + kötőjel/kettőspont + alfanumerikus (min 4 char)
    (r"\b[A-Za-z0-9]{2,}[\-:][A-Za-z0-9\-:]{4,25}\b", 0.75),
    # Számok kötőjellel/kettősponttal: 123-456, 123:456
    (r"\b\d{3,}[\-:]\d{2,}[\w\-:]*\b", 0.72),
    # 5+ egymást követő számjegy
    (r"\b\d{5,}\b", 0.60),
    # 4 jegyű szám (házszám pl. lives at 1600) – évszám kizárva
    (r"\b\d{4}\b", 0.55),
    # GPS koordináta pár: 47.4979, 19.0402 vagy 47.5, 19.0
    (r"\b-?\d{1,3}\.\d{1,6}\s*,\s*-?\d{1,3}\.\d{1,6}\b", 0.72),
]

# Kulcsszavak: substringként is (motorszám tartalmazza a „szám”-ot)
# HU, EN, ES + elírások (cim, szam, alvazszam) + cím kulcsszavak
_IDENTIFIER_KEYWORDS_REGEX = re.compile(
    r"(?i)"
    r"(?:"
    r"motorsz[áa]m|alv[áa]zsz[áa]m|rendsz[áa]m|"
    r"azonos[íi]t[oó]|sz[áa]m(?:a|á)?|"
    r"c[íi]m|koordin[áa]ta|"
    r"identifier|device\s+id|user\s+id|cookie\s+id|"
    r"\btag\b|address|ticket|coordinate|ciirtdinates|"
    r"number|numero|n[uú]mero|número\s+de|"
    r"gps|lives\s+at|"
    r"direcci[oó]n|dispositivo|"
    r"asset\s+tag|hostname|"
    r"número\s+de\s+cliente|número\s+de\s+contrato|iban|fizetés|payment|"
    r"printer\s+asset|network\s+identifier|"
    r"recovery\s+code|billing\s+account|"
    r"claim\s+number|audit\s+azonosító|"
    r"flottakód|ügyfélazonosító|"
    r"jogosítványszám|útlevélszáma|"
    r"személyi\s+igazolvány|"
    # Cím kulcsszavak: épület, út, tér, emelet, köz, kerület, ajtó, város, stb.
    r"épület|epulet|útja?|utja?|tér|ter|utca|planta|puerta|unit|"
    r"lph|lépcsház|lepcshaz|emelet|köz|koz|negyed|"
    r"kerület|kerulet|ajtó|ajto|város|varos|"
    r"körút|sugárút|sétány|rakpart|liget|park|"
    r"lakótelep|telep|major|tanya|zug|zsákutca|"
    r"hrsz|helyrajzi\s+szám|"
    r"street|avenue|road|boulevard|drive|lane|way|court|"
    r"building|floor|apt|apartment|suite|district|quarter|city|"
    r"calle|plaza|paseo|edificio|piso|puerta|distrito|barrio|ciudad"
    r")"
)

# Ablak: ennyi karakter előtte/utána nézzük a kulcsszavakat
_CONTEXT_BEFORE = 120
_CONTEXT_AFTER = 80


def _get_context(text: str, start: int, end: int) -> str:
    ctx_start = max(0, start - _CONTEXT_BEFORE)
    ctx_end = min(len(text), end + _CONTEXT_AFTER)
    return text[ctx_start:ctx_end]


def _infer_with_priority(
    text: str, start: int, end: int, matched: str
) -> Optional[EntityType]:
    """
    Prioritás: kulcsszó előtte → utána → bővített előtte (mondat eleje) → bővített utána (mondat vége).
    Ha egyik sem ad azonosítót → None (hagyja).
    """
    ctx_before = text[max(0, start - _CONTEXT_BEFORE) : start]
    ctx_after = text[end : min(len(text), end + _CONTEXT_AFTER)]
    # 1. Előtte
    chunk = ctx_before[-80:] + " " + matched
    if _IDENTIFIER_KEYWORDS_REGEX.search(chunk):
        return _infer_entity_type(chunk + " " + ctx_after[:40])
    # 2. Utána
    chunk = matched + " " + ctx_after[:80]
    if _IDENTIFIER_KEYWORDS_REGEX.search(chunk):
        return _infer_entity_type(ctx_before[-40:] + " " + chunk)
    # 3. Teljes előtte
    if _IDENTIFIER_KEYWORDS_REGEX.search(ctx_before + " " + matched):
        return _infer_entity_type(ctx_before + " " + matched + " " + ctx_after[:40])
    # 4. Teljes utána
    if _IDENTIFIER_KEYWORDS_REGEX.search(matched + " " + ctx_after):
        return _infer_entity_type(ctx_before[-40:] + " " + matched + " " + ctx_after)
    return None


def _is_likely_year(num_str: str) -> bool:
    """19xx vagy 20xx évszám – ne detektáljuk azonosítónak."""
    if len(num_str) != 4 or not num_str.isdigit():
        return False
    return num_str.startswith("19") or num_str.startswith("20")


# Dátum kontextus: ha ezek megjelennek, NE adjunk vissza POSTAL_ADDRESS dátum alakú számra
_DATE_NEGATIVE_CONTEXT = re.compile(
    r"(?i)\b(?:szül\.?|született|dob|fecha\s+de\s+nacimiento|date\s+of\s+birth|born)\b"
)

_DATE_SHAPE_PATTERN = re.compile(
    r"^(?:19|20)\d{2}[.\-/](?:0[1-9]|1[0-2])[.\-/](?:0[1-9]|[12]\d|3[01])$|"
    r"^(?:0[1-9]|[12]\d|3[01])[.\-/](?:0[1-9]|1[0-2])[.\-/](?:19|20)\d{2}$"
)


def _is_date_shaped(matched: str) -> bool:
    clean = re.sub(r"\s+", "", matched)
    return bool(_DATE_SHAPE_PATTERN.match(clean))


def _infer_entity_type(context: str) -> EntityType:
    """Kontextus alapján becsüli a legvalószínűbb entitástípust."""
    ctx_lower = context.lower()
    if re.search(r"motor|engine|motorsz", ctx_lower):
        return EntityType.ENGINE_IDENTIFIER
    if re.search(r"alv[áa]z|chassis|chasis", ctx_lower):
        return EntityType.CHASSIS_IDENTIFIER
    if re.search(r"device|dispositivo|hostname|tag|printer|asset", ctx_lower):
        return EntityType.DEVICE_ID
    if re.search(r"ticket|claim|audit|jegy|caso", ctx_lower):
        return EntityType.TICKET_ID
    if re.search(r"iban|fizetés|payment|számla", ctx_lower) and re.search(
        r"\b[A-Z]{2}\d{2}", ctx_lower
    ):
        return EntityType.IBAN
    if re.search(r"rendsz[áa]m|matr[íi]cula|plate|registration", ctx_lower):
        return EntityType.VEHICLE_REGISTRATION
    if re.search(r"személyi\s+igazolv|személyi\s+igazolvány|dni|nie", ctx_lower):
        return EntityType.PERSONAL_ID
    if re.search(r"útlevél|pasaport|passport", ctx_lower):
        return EntityType.PASSPORT_NUMBER
    if re.search(r"jogosítvány|permiso\s+de\s+conducir|driver\s+license", ctx_lower):
        return EntityType.DRIVER_LICENSE_NUMBER
    if re.search(r"user\s+id|userid|felhasználói\s+azonosító", ctx_lower):
        return EntityType.USER_ID
    if re.search(r"cookie\s+id|cookieid", ctx_lower):
        return EntityType.COOKIE_ID
    if re.search(r"iban|fizetés|payment|számla", ctx_lower):
        return EntityType.IBAN
    if re.search(r"coordinate|ciirtdinates|gps|koordin", ctx_lower):
        return EntityType.POSTAL_ADDRESS
    if re.search(
        r"address|c[íi]m|direcci|lives\s+at|utca|út|tér|emelet|épület|"
        r"kerület|ajtó|város|street|avenue|road|calle|building|edificio|piso|apt\b",
        ctx_lower,
    ):
        return EntityType.POSTAL_ADDRESS
    if re.search(r"contract|contrato|szerz[őo]d[eé]s|número\s+de\s+contrato", ctx_lower):
        return EntityType.CONTRACT_NUMBER
    if re.search(r"ad[oó]azonosító|tax\s+id|nif", ctx_lower):
        return EntityType.TAX_ID
    if re.search(r"customer|cliente|ügyfél", ctx_lower):
        return EntityType.CUSTOMER_ID
    return EntityType.CUSTOMER_ID  # fallback


class ContextNumberRecognizer(BaseDetector):
    """
    Számokat keres a szövegben; ha a közelben (előtte/utána) azonosítóra utaló
    kulcsszó van (akár egybeírva: motorszám, jogosítványszám), detektálja.
    """

    name = "context_number_recognizer"

    def detect(self, text: str, language: str = "en") -> List[DetectionResult]:
        results: List[DetectionResult] = []
        seen_spans: set[Tuple[int, int]] = set()

        for pattern_str, base_conf in _NUMBER_ID_PATTERNS:
            for m in re.finditer(pattern_str, text):
                start, end = m.start(), m.end()
                if (start, end) in seen_spans:
                    continue
                matched = m.group(0)
                # 4 jegyű: évszámot ne (19xx, 20xx)
                if len(matched) == 4 and matched.isdigit() and _is_likely_year(matched):
                    continue
                entity_type = _infer_with_priority(text, start, end, matched)
                if entity_type is None:
                    continue  # Nem sikerült azonosítani → hagyja
                # Dátum kontextus + dátum alakú szám → NE legyen POSTAL_ADDRESS
                context = _get_context(text, start, end)
                if _DATE_NEGATIVE_CONTEXT.search(context) and _is_date_shaped(matched):
                    if entity_type == EntityType.POSTAL_ADDRESS:
                        entity_type = EntityType.DATE_OF_BIRTH
                conf = base_conf
                # Cím/address kontextus: 4 jegyű házszám – emeljük a konfidenciát
                if len(matched) == 4 and re.search(r"(?i)lives\s+at|address|c[íi]m|direcci", context):
                    conf = max(conf, 0.65)
                seen_spans.add((start, end))
                results.append(
                    DetectionResult(
                        entity_type=entity_type,
                        matched_text=matched,
                        start=start,
                        end=end,
                        language=language,
                        source_detector=self.name,
                        confidence_score=conf,
                        risk_level=RiskClass.INDIRECT_IDENTIFIER,
                        recommended_action=RecommendedAction.REVIEW_REQUIRED,
                    )
                )
        return results
