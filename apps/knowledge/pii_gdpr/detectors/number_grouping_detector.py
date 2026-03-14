# apps/knowledge/pii_gdpr/detectors/number_grouping_detector.py
"""
Optimalizált rutin: először a számokat nézi, majd az előtte/utána lévő szavakat.
Ha a környező szavakban is vannak számok, összevonja egy blokkba.
Prioritás: kulcsszó előtte → kulcsszó utána → mondat eleje → mondat vége. Ha egyik sem: hagyja.
Cím/helység kulcsszavak + számok egybe. Kötőjel / vagy : számok között = egy egység.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

from apps.knowledge.pii_gdpr.enums import EntityType, RiskClass, RecommendedAction
from apps.knowledge.pii_gdpr.models import DetectionResult
from apps.knowledge.pii_gdpr.detectors.base import BaseDetector


# Token: \S+ (nem-whitespace) – kötőjel/: számok egy szó (18-24, 123:456)
_TOKEN_RE = re.compile(r"\S+")

# Szó tartalmaz számot
_HAS_DIGIT = re.compile(r"\d")

# Kötőjel, kettőspont vagy / önmagában is összekötő (18-24, 123:456, 2/7 egy egység)
# Cím/helység kulcsszavak: épület, út, emelet, ajtó, város, tér, utca, street, calle stb.
_CONNECTOR_WORDS = re.compile(
    r"(?i)^(?:[\-:/]|"
    r"épület|epulet|út|ut|útja|utja|emelet|köz|koz|kerület|kerulet|ajtó|ajto|"
    r"város|varos|tér|ter|utca|lph|lépcsház|lepcshaz|negyed|"
    r"körút|sugárút|sétány|rakpart|liget|park|"
    r"building|floor|apt|apartment|suite|district|quarter|city|"
    r"street|avenue|road|calle|plaza|edificio|piso|puerta|distrito|barrio|ciudad|"
    r"január|február|március|április|május|június|július|augusztus|"
    r"szeptember|október|november|december|"
    r"january|february|march|april|may|june|july|august|"
    r"september|october|november|december|"
    r"enero|febrero|marzo|abril|mayo|junio|julio|agosto|"
    r"septiembre|octubre|noviembre|diciembre"
    r")$"
)

# Azonosítóra utaló kulcsszavak a mondatrészben vagy a csoportban
_IDENTIFIER_HINTS = re.compile(
    r"(?i)"
    r"(?:motorsz[áa]m|alv[áa]zsz[áa]m|rendsz[áa]m|azonos[íi]t[oó]|sz[áa]m(?:a|á)?|"
    r"c[íi]m|koordin[áa]ta|identifier|device\s+id|user\s+id|cookie\s+id|"
    r"tag|address|ticket|coordinate|gps|lives\s+at|direcci[oó]n|dispositivo|"
    r"asset\s+tag|hostname|número\s+de\s+cliente|número\s+de\s+contrato|"
    r"épület|epulet|út|ut|emelet|köz|kerület|ajtó|város|tér|utca|"
    r"street|avenue|road|building|floor|calle|plaza|edificio|piso|planta|puerta|unit|"
    r"contract|contrato|szerz[őo]d[eé]s|ad[oó]azonosító|tax\s+id|nif|"
    r"customer|cliente|ügyfél|született|szül\.?|dob|date\s+of\s+birth|"
    r"személyi|igazolvány|útlevél|iban|fizetés|payment|jogosítvány|"
    r"orvosi|vizsgálat|január|február|március|április|május|június|július|"
    r"augusztus|szeptember|október|november|december|january|february|march)"
)


@dataclass
class Token:
    text: str
    start: int
    end: int

    @property
    def has_digit(self) -> bool:
        return bool(_HAS_DIGIT.search(self.text))

    @property
    def is_connector(self) -> bool:
        return bool(_CONNECTOR_WORDS.match(self.text))


def _tokenize(text: str) -> List[Token]:
    tokens: List[Token] = []
    for m in _TOKEN_RE.finditer(text):
        tokens.append(Token(text=m.group(0), start=m.start(), end=m.end()))
    return tokens


def _get_sentence_boundaries(text: str) -> List[Tuple[int, int]]:
    """Mondathatárok: . ! ? \n alapján."""
    boundaries: List[Tuple[int, int]] = []
    start = 0
    for m in re.finditer(r"[.!?\n]+", text):
        boundaries.append((start, m.end()))
        start = m.end()
    if start < len(text):
        boundaries.append((start, len(text)))
    return boundaries


def _group_number_tokens(tokens: List[Token]) -> List[List[Token]]:
    """
    Csoportosítja az egymás mellett lévő számos szavakat.
    Köztes összekötő szavak (épület, út, emelet) belekerülnek a csoportba.
    """
    groups: List[List[Token]] = []
    i = 0
    while i < len(tokens):
        if not tokens[i].has_digit:
            i += 1
            continue
        group = [tokens[i]]
        j = i + 1
        while j < len(tokens):
            if tokens[j].has_digit:
                group.append(tokens[j])
                j += 1
            elif tokens[j].is_connector and j + 1 < len(tokens) and tokens[j + 1].has_digit:
                group.append(tokens[j])
                group.append(tokens[j + 1])
                j += 2
            else:
                break
        groups.append(group)
        i = j
    return groups


def _infer_entity_type_from_context(context_words: str) -> EntityType:
    """A legközelebbi megtalált szó alapján azonosító típus."""
    ctx_lower = context_words.lower()
    if re.search(r"motor|engine|motorsz", ctx_lower):
        return EntityType.ENGINE_IDENTIFIER
    if re.search(r"alv[áa]z|chassis|chasis", ctx_lower):
        return EntityType.CHASSIS_IDENTIFIER
    if re.search(r"device|dispositivo|hostname|tag|printer|asset", ctx_lower):
        return EntityType.DEVICE_ID
    if re.search(r"ticket|claim|audit|jegy|caso", ctx_lower):
        return EntityType.TICKET_ID
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
    if re.search(r"coordinate|gps|koordin", ctx_lower):
        return EntityType.POSTAL_ADDRESS
    if re.search(
        r"address|c[íi]m|direcci|lives\s+at|utca|út|tér|emelet|épület|"
        r"kerület|ajtó|város|street|avenue|road|calle|building|edificio|piso|apt\b",
        ctx_lower,
    ):
        return EntityType.POSTAL_ADDRESS
    if re.search(r"született|szül\.?|dob|date\s+of\s+birth", ctx_lower):
        return EntityType.DATE_OF_BIRTH
    if re.search(
        r"január|február|március|április|május|június|július|augusztus|"
        r"szeptember|október|november|december|january|february|march",
        ctx_lower,
    ):
        return EntityType.DATE
    if re.search(r"contract|contrato|szerz[őo]d[eé]s|número\s+de\s+contrato", ctx_lower):
        return EntityType.CONTRACT_NUMBER
    if re.search(r"ad[oó]azonosító|tax\s+id|nif", ctx_lower):
        return EntityType.TAX_ID
    if re.search(r"customer|cliente|ügyfél", ctx_lower):
        return EntityType.CUSTOMER_ID
    return EntityType.CUSTOMER_ID  # fallback


def _infer_entity_type_with_priority(
    ctx_before: str,
    ctx_after: str,
    matched: str,
) -> Optional[EntityType]:
    """
    Prioritás: 1) kulcsszó előtte, 2) utána, 3) mondat elejéig (teljes előtte),
    4) mondat végéig (teljes utána). Ha egyik sem ad azonosítót → None (hagyja).
    """
    # 1. Közvetlenül előtte lévő szavak
    chunk = (ctx_before[-80:] if len(ctx_before) > 80 else ctx_before) + " " + matched
    if _IDENTIFIER_HINTS.search(chunk):
        return _infer_entity_type_from_context(chunk + " " + ctx_after[:40])
    # 2. Közvetlenül utána lévő szavak
    chunk = matched + " " + (ctx_after[:80] if len(ctx_after) > 80 else ctx_after)
    if _IDENTIFIER_HINTS.search(chunk):
        return _infer_entity_type_from_context(ctx_before[-40:] + " " + chunk)
    # 3. Teljes mondatrész előtte (mondat elejéig)
    chunk = ctx_before + " " + matched
    if _IDENTIFIER_HINTS.search(chunk):
        return _infer_entity_type_from_context(chunk + " " + ctx_after[:40])
    # 4. Teljes mondatrész utána (mondat végéig)
    chunk = matched + " " + ctx_after
    if _IDENTIFIER_HINTS.search(chunk):
        return _infer_entity_type_from_context(ctx_before[-40:] + " " + chunk)
    return None


def _is_likely_year(s: str) -> bool:
    if len(s) != 4 or not s.isdigit():
        return False
    return s.startswith("19") or s.startswith("20")


# Dátum kontextus: ha ezek megjelennek, NE adjunk vissza POSTAL_ADDRESS
_DATE_NEGATIVE_CONTEXT = re.compile(
    r"(?i)\b(?:szül\.?|született|dob|fecha\s+de\s+nacimiento|date\s+of\s+birth|born)\b"
)

# Dátumszerű szám: YYYY-MM-DD, DD/MM/YYYY, YYYY.MM.DD
_DATE_SHAPE_PATTERN = re.compile(
    r"^(?:19|20)\d{2}[.\-/](?:0[1-9]|1[0-2])[.\-/](?:0[1-9]|[12]\d|3[01])$|"
    r"^(?:0[1-9]|[12]\d|3[01])[.\-/](?:0[1-9]|1[0-2])[.\-/](?:19|20)\d{2}$"
)


def _is_date_shaped(matched: str) -> bool:
    """Dátumszerű szám: 1989-08-17, 17/08/1989."""
    clean = re.sub(r"\s+", "", matched)
    return bool(_DATE_SHAPE_PATTERN.match(clean))


class NumberGroupingDetector(BaseDetector):
    """
    Első fázis: számot tartalmazó szavak csoportosítása.
    Egymás mellett lévő számos szavak + összekötők egy blokk.
    A mondatrész kontextusából (előtte/utána szavak) az azonosító típusa.
    """

    name = "number_grouping"

    def detect(self, text: str, language: str = "en") -> List[DetectionResult]:
        results: List[DetectionResult] = []
        tokens = _tokenize(text)
        groups = _group_number_tokens(tokens)
        sentence_bounds = _get_sentence_boundaries(text)

        for group in groups:
            if not group:
                continue
            start = group[0].start
            end = group[-1].end
            matched = text[start:end]

            # 4 jegyű évszám kizárása (19xx, 20xx) ha nincs dátum kontextus
            if len(matched) <= 6 and matched.replace(" ", "").replace(".", "").isdigit():
                parts = re.findall(r"\d+", matched)
                if len(parts) == 1 and _is_likely_year(parts[0]):
                    continue

            # Mondatrész: melyik mondatba esik
            sentence_start, sentence_end = start, end
            for s_start, s_end in sentence_bounds:
                if s_start <= start < s_end:
                    sentence_start, sentence_end = s_start, s_end
                    break

            # Kontextus: mondatrész szavai – prioritás: előtte → utána → mondat eleje → mondat vége
            ctx_before = text[max(0, sentence_start) : start]
            ctx_after = text[end : min(len(text), sentence_end)]

            entity_type = _infer_entity_type_with_priority(ctx_before, ctx_after, matched)
            if entity_type is None:
                continue  # Nem sikerült azonosítani → hagyja
            # Dátum kontextus + dátum alakú szám → NE legyen POSTAL_ADDRESS
            context_words = ctx_before + " " + matched + " " + ctx_after
            if _DATE_NEGATIVE_CONTEXT.search(context_words) and _is_date_shaped(matched):
                if entity_type == EntityType.POSTAL_ADDRESS:
                    entity_type = EntityType.DATE_OF_BIRTH
            confidence = 0.78

            results.append(
                DetectionResult(
                    entity_type=entity_type,
                    matched_text=matched,
                    start=start,
                    end=end,
                    language=language,
                    source_detector=self.name,
                    confidence_score=confidence,
                    risk_level=RiskClass.INDIRECT_IDENTIFIER,
                    recommended_action=RecommendedAction.REVIEW_REQUIRED,
                )
            )
        return results
