# apps/knowledge/pii_gdpr/pipeline/span_extender.py
"""
Span kiterjesztés: ha számok között csak szóköz, írásjel vagy összekötő szó van
(épület, út, emelet, ajtó, február stb.), az egész blokkot egy azonosítónak kezeljük.
A szóköz nem a vége – csak akkor, ha utána nincs szám.
"""
from __future__ import annotations

import re
from typing import List

from apps.knowledge.pii_gdpr.enums import EntityType, RiskClass, RecommendedAction
from apps.knowledge.pii_gdpr.models import DetectionResult


# Címtípusú szavak számok között – címblokk egybe (HU + EN + ES)
# Rövidítések ponttal: (?:\b|$) a végén
_ADDRESS_BLOCK_WORDS = re.compile(
    r"(?i)(?:"
    # Betű + épület/lépcsőház/szárny/blokk (pl. A épület, B lépcsőház, C szárny)
    r"\b[A-Z]\s+(?:épület|epulet|lépcsház|lepcshaz|lépcsőház|lepcsőhaz|szárny|szarny|blokk)\b|"
    # EN: Building A, Block B, Floor 4, 4th Floor, Apt 4B, Flat 2, Unit 2/7, Suite 300
    r"\b(?:Building|Block)\s+[A-Z]\b|"
    r"\b(?:Floor|Flat)\s+\d+[A-Z]?\b|"
    r"\b\d+(?:st|nd|rd|th)\s+Floor\b|"
    r"\b(?:Apartment|Apt|Flat|Unit|Suite)\s+[\w/\-\.]+\b|"
    # ES: Edificio A, Portal A, Planta 3, Piso 2, Puerta 2/7, Bloque C, Escalera B, 4º piso
    r"\b(?:Edificio|Portal|Bloque|Escalera)\s+[A-Z]\b|"
    r"\b(?:Planta|Piso)\s+\d+\b|"
    r"\b\d+º?\s*(?:piso|planta)\b|"
    r"\bPuerta\s+\d+(?:\s*/\s*\d+)?\b|"
    # Ordinalis + emelet/ajtó (pl. 4. emelet, II. emelet, 2/7. ajtó)
    r"\b\d+\s*\.?\s*(?:emelet|epulet|ajtó|ajto)\b|"
    r"\b\d+\s*/\s*\d+\s*\.?\s*(?:ajtó|ajto)\b|"
    r"\b(?:II?|III?|IV|V|VI?|VII?|VIII|IX|XI?|XII)\s*\.?\s*(?:emelet|epulet)\b|"
    # HU: épület, emelet, ajtó, lépcsőház + közterület
    r"\b(?:épület|epulet|emelet|ajtó|ajto|"
    r"lépcsház|lepcshaz|lépcsőház|lepcsőhaz|szárny|szarny|blokk|"
    r"utca|út|ut|útja|utja|tér|ter|tere|"
    r"körút|körútja|körönd|sugárút|sétány|sor|köz|koz|köze|"
    r"fasor|dűlő|lejtő|rakpart|part|liget|park|"
    r"lakótelep|telep|major|tanya|zug|zsákutca|átjáró|"
    r"határút|bekötőút|ipartelep|pincesor|külterület|"
    r"building|floor|apt|apartment|suite|flat|unit|block|"
    r"edificio|piso|puerta|planta|portal|bloque|escalera|distrito|barrio)\b|"
    r"\b(?:ép\.?|ep\.?|em\.?|fsz\.?|lph\.?|hrsz\.?)(?:\b|$)|"
    r"\b(?:helyrajzi\s+szám|alsó\s+sor|felső\s+sor|alsó\s+utca|felső\s+utca|"
    r"összekötő\s+út|elkerülő\s+út|vasút\s+sor|vasút\s+utca|ipari\s+park)\b|"
    # EN: street, st., road, avenue, boulevard, lane, drive, court, square, place, ...
    r"\b(?:street|road|avenue|boulevard|lane|drive|court|square|place|terrace|"
    r"way|close|crescent|parkway|highway|walk|mews|gardens|garden|grove|row|"
    r"hill|bridge|embankment|quay|alley|bypass|estate)\b|"
    r"\b(?:st\.?|rd\.?|ave\.?|blvd\.?|ln\.?|dr\.?|ct\.?|sq\.?|pl\.?|ter\.?|"
    r"cres\.?|pkwy\.?|hwy\.?|industrial\s+estate)(?:\b|$)|"
    r"\b(?:ring\s+road|service\s+road)\b|"
    # ES: calle, c., avenida, av., paseo, plaza, camino, carretera, ...
    r"\b(?:calle|avenida|paseo|plaza|camino|carretera|"
    r"ronda|travesía|travesia|pasaje|glorieta|cuesta|bajada|subida|"
    r"parque|urbanización|urbanizacion|bulevar|vía|via|rambla|sendero|"
    r"barrio|polígono|poligono|muelle|costanilla|carrera|autovía|autovia|autopista|edificio)\b|"
    r"\b(?:c\.?|av\.?|pl\.?)(?:\b|$)"
    r")"
)

# Összekötő szavak számok között: épület, út, emelet, ajtó, kötőjel, :, / stb.
# Betű + épület (A épület, B lépcsőház) – extend_adjacent_spans számára
_CONNECTOR_WORDS = re.compile(
    r"(?i)(?:^[\-:/]|"
    r"\b[A-Z]\s+(?:épület|epulet|lépcsház|lepcshaz|lépcsőház|lepcsőhaz|szárny|szarny|blokk)\b|"
    r"\b(?:"
    r"épület|epulet|út|ut|útja|utja|emelet|köz|koz|kerület|kerulet|ajtó|ajto|"
    r"város|varos|tér|ter|utca|lph|lépcsház|lepcshaz|negyed|"
    r"körút|sugárút|sétány|rakpart|liget|park|"
    r"building|floor|apt|apartment|suite|flat|unit|block|district|quarter|city|"
    r"street|avenue|road|calle|plaza|edificio|piso|puerta|planta|portal|bloque|escalera|distrito|barrio|ciudad|"
    # Hónapnevek – dátum részeként (pl. 2025. február 18)
    r"január|február|március|április|május|június|július|augusztus|"
    r"szeptember|október|november|december|"
    r"january|february|march|april|may|june|july|august|"
    r"september|october|november|december|"
    r"enero|febrero|marzo|abril|mayo|junio|julio|agosto|"
    r"septiembre|octubre|noviembre|diciembre"
    r")\b)"
)

# Szám: \d+ kötőjellel vagy : elválasztva összetartozó (18-24, 123:456)
_NUMBER_RE = re.compile(r"\d+[a-z]?(?:\s*[./\-:]\s*\d+(?:\s*/\s*\d+)?\.?)*|\d+")

# Magyar közterület típusok – az előtte lévő szó az utca neve
_STREET_TYPE_HU = re.compile(
    r"(?i)\b(?:utca|út|útja|tér|tere|körút|körútja|sugárút|sétány|rakpart|"
    r"liget|park|köz|sor|fasor|dűlő|lejtő|part|lakótelep|telep|major|tanya|"
    r"zug|zsákutca|átjáró)\b"
)

# ES/EN közterület típusok – az utána lévő szó az utca neve (Calle Mayor, Street Name)
_STREET_TYPE_ES_EN = re.compile(
    r"(?i)\b(?:calle|plaza|plazoleta|avenida|av\.?|paseo|camino|carretera|"
    r"street|st\.?|avenue|ave\.?|road|rd\.?|boulevard|blvd\.?|drive|dr\.?|"
    r"lane|ln\.?|way|court|ct\.?)\b"
)

# Szó: nem-whitespace
_WORD_RE = re.compile(r"\S+")

# Rövidített cím kontextus: "Város, Név " (pl. Budapest, Keleti Károly )
_SHORT_ADDRESS_CONTEXT = re.compile(
    r"(?i)\b[A-ZÁÉÍÓÖÜŐÚa-záéíóöüőú]+\s*,\s*[A-ZÁÉÍÓÖÜŐÚa-záéíóöüőú\s]{3,}"
)


def _has_digit(s: str) -> bool:
    return bool(re.search(r"\d", s))


def _is_extendable_type(entity_type: EntityType) -> bool:
    """Ezek a típusok kiterjeszthetők (szám/cím/dátum jellegű)."""
    return entity_type in (
        EntityType.POSTAL_ADDRESS,
        EntityType.DATE,
        EntityType.DATE_OF_BIRTH,
        EntityType.CUSTOMER_ID,
        EntityType.CONTRACT_NUMBER,
        EntityType.TICKET_ID,
        EntityType.DEVICE_ID,
        EntityType.PERSONAL_ID,
        EntityType.TAX_ID,
        EntityType.ENGINE_IDENTIFIER,
        EntityType.CHASSIS_IDENTIFIER,
    )


def _extend_right(text: str, end: int, max_chars: int = 80) -> int:
    """
    Kiterjeszt jobbra: ha end után szám van (köztes szóköz/írásjel/összekötő szó),
    visszaadja az új end pozíciót.
    """
    rest = text[end : end + max_chars]
    pos = 0
    while pos < len(rest):
        # Szóköz, írásjel
        m = re.match(r"[\s.,;:\-/]+", rest[pos:])
        if m:
            pos += m.end()
            continue
        # Összekötő szó
        m = _CONNECTOR_WORDS.match(rest[pos:])
        if m:
            pos += m.end()
            continue
        # Szám – kiterjesztünk
        m = _NUMBER_RE.match(rest[pos:])
        if m:
            return end + pos + m.end()
        break
    return end


def _extend_left(text: str, start: int, max_chars: int = 80) -> int:
    """
    Kiterjeszt balra: ha start előtt szám van (köztes szóköz/írásjel/összekötő szó),
    visszaadja az új start pozíciót.
    """
    chunk = text[max(0, start - max_chars) : start]
    # Visszafelé keresünk
    for m in list(_NUMBER_RE.finditer(chunk))[::-1]:
        num_end = m.end()
        between = chunk[num_end:]
        # Köztes rész: csak szóköz, írásjel, összekötő
        between_clean = re.sub(r"[\s.,;:\-/]+", " ", between)
        between_clean = _CONNECTOR_WORDS.sub(" ", between_clean)
        if re.match(r"^[\s]*$", between_clean):
            return start - len(chunk) + m.start()
    return start


def _extend_address_street_name(
    text: str, start: int, end: int, language: str
) -> tuple[int, int]:
    """
    Cím span kiterjesztése: utca név bevonása.
    HU: közterület típus (út, utca, tér) előtti szó = utca neve → balra.
    ES: típus utáni szó (Calle Mayor) → balra (típus+név a szám előtt).
    EN: típus előtti szó (Main Street) → balra vagy jobbra (123 Main Street → jobbra).
    """
    new_start, new_end = start, end
    chunk_before = text[max(0, start - 100) : start]
    chunk_after = text[end : min(len(text), end + 100)]

    # Magyar: típus előtti szó (Szabadság út 22)
    for m in list(_STREET_TYPE_HU.finditer(chunk_before))[::-1]:
        before_type = chunk_before[: m.start()].rstrip()
        last_word = list(_WORD_RE.finditer(before_type))
        if last_word:
            ns = start - len(chunk_before) + last_word[-1].start()
            if start - ns <= 80:
                new_start = ns
        break

    # ES: típus + utána lévő szó (Calle Mayor 12)
    if language in ("es", "spa"):
        for m in list(_STREET_TYPE_ES_EN.finditer(chunk_before))[::-1]:
            after_type = chunk_before[m.end() :].lstrip()
            if _WORD_RE.match(after_type):
                ns = start - len(chunk_before) + m.start()
                if start - ns <= 80:
                    new_start = min(new_start, ns)
            break

    # EN: típus előtti szó (Main Street 123) vagy típus+előtte (123 Main Street)
    if language in ("en", "eng"):
        # Előtte: Main Street 123
        for m in list(_STREET_TYPE_ES_EN.finditer(chunk_before))[::-1]:
            before_type = chunk_before[: m.start()].rstrip()
            last_word = list(_WORD_RE.finditer(before_type))
            if last_word:
                ns = start - len(chunk_before) + last_word[-1].start()
                if start - ns <= 80:
                    new_start = min(new_start, ns)
            break
        # Utána: 123 Main Street
        for m in _STREET_TYPE_ES_EN.finditer(chunk_after):
            before_in_after = chunk_after[: m.start()].rstrip()
            last_word = list(_WORD_RE.finditer(before_in_after))
            if last_word:
                ne = end + last_word[-1].end()
                if ne - end <= 80:
                    new_end = max(new_end, ne)
            break

    return new_start, new_end


def extend_address_street_names(
    text: str, detections: List[DetectionResult]
) -> List[DetectionResult]:
    """Cím detekciók kiterjesztése: utca név bevonása (HU: előtte, ES/EN: utána/többnyire)."""
    result: List[DetectionResult] = []
    for d in detections:
        if d.entity_type != EntityType.POSTAL_ADDRESS:
            result.append(d)
            continue
        new_start, new_end = _extend_address_street_name(
            text, d.start, d.end, d.language or "en"
        )
        if new_start < d.start or new_end > d.end:
            new_text = text[new_start:new_end]
            result.append(
                DetectionResult(
                    entity_type=d.entity_type,
                    matched_text=new_text,
                    start=new_start,
                    end=new_end,
                    language=d.language,
                    source_detector=d.source_detector,
                    confidence_score=d.confidence_score,
                    risk_level=d.risk_level,
                    recommended_action=d.recommended_action,
                )
            )
        else:
            result.append(d)
    return result


def _extend_right_address_block(text: str, end: int, max_chars: int = 120) -> int:
    """Jobbra kiterjeszt: cím szavak (emelet, épület, ajtó, lépcsőház) + szám.
    A épület, 4. emelet, 2/7. ajtó stb. is belekerülnek."""
    rest = text[end : end + max_chars]
    pos = 0
    while pos < len(rest):
        m = re.match(r"[\s.,;:\-/]+", rest[pos:])
        if m:
            pos += m.end()
            continue
        m = _ADDRESS_BLOCK_WORDS.match(rest[pos:])
        if m:
            pos += m.end()
            continue
        m = _NUMBER_RE.match(rest[pos:])
        if m:
            return end + pos + m.end()
        break
    return end + pos  # Kiterjesztés cím szavakon keresztül (pl. A épület, 4. emelet)


def _extend_left_address_block(text: str, start: int, max_chars: int = 120) -> int:
    """Balra kiterjeszt: csak cím szavak + szám."""
    chunk = text[max(0, start - max_chars) : start]
    for m in list(_NUMBER_RE.finditer(chunk))[::-1]:
        between = chunk[m.end() :]
        between_clean = re.sub(r"[\s.,;:\-/]+", " ", between)
        between_clean = _ADDRESS_BLOCK_WORDS.sub(" ", between_clean)
        if re.match(r"^[\s]*$", between_clean):
            return start - len(chunk) + m.start()
    return start


def _extend_block_left_with_address_words(text: str, start: int, max_chars: int = 60) -> int:
    """Balra: cím szavak + közvetlenül előttük lévő szó (pl. B épület, 2. emelet)."""
    chunk = text[max(0, start - max_chars) : start].rstrip()
    if not chunk:
        return start
    words = list(_WORD_RE.finditer(chunk))
    if not words:
        return start
    # Utolsó cím szó a blokk előtt
    last_addr_pos = -1
    for i in range(len(words) - 1, -1, -1):
        if _ADDRESS_BLOCK_WORDS.match(words[i].group()):
            last_addr_pos = i
            break
    if last_addr_pos < 0:
        return start
    # Cím szó + közvetlenül előtte lévő szó (pl. B épület)
    include_from = max(0, last_addr_pos - 1)
    new_start = start - len(chunk) + words[include_from].start()
    return new_start


def _extend_block_right_with_address_words(text: str, end: int, max_chars: int = 80) -> int:
    """Jobbra: cím szavak az utolsó szám után (pl. 3/12. ajtó, fsz. 2).
    Iteratívan kiterjeszt, amíg cím szavak + számok következnek."""
    new_end = end
    for _ in range(5):
        chunk = text[new_end : new_end + max_chars]
        rest = chunk.lstrip()
        if not rest:
            break
        m = _ADDRESS_BLOCK_WORDS.match(rest)
        if m:
            start_offset = len(chunk) - len(rest)
            new_end += start_offset + m.end()
        else:
            break
    return new_end


def find_address_blocks(text: str, language: str = "en") -> List[DetectionResult]:
    """
    Címblokkok keresése: ha szám előtt/után emelet, épület, ajtó, lépcsőház stb. van,
    az első és utolsó szám közötti részek mind a címhez tartoznak.
    Csak címtípusú szavak állhatnak a számok között.
    """
    results: List[DetectionResult] = []
    seen: set[tuple[int, int]] = set()

    for m in _NUMBER_RE.finditer(text):
        start, end = m.start(), m.end()
        # Van-e cím szó a közelben (előtte/utána 80 char)?
        ctx_before = text[max(0, start - 80) : start]
        ctx_after = text[end : min(len(text), end + 80)]
        has_addr = _ADDRESS_BLOCK_WORDS.search(ctx_before) or _ADDRESS_BLOCK_WORDS.search(
            ctx_after
        )
        # Rövidített cím: "Város, Név 18-24" (pl. Budapest, Keleti Károly)
        has_short_addr = _SHORT_ADDRESS_CONTEXT.search(ctx_before)
        if not has_addr and not has_short_addr:
            continue
        used_short_context = has_short_addr and not has_addr

        # Kiterjesztés: első szám → utolsó szám (köztes: csak cím szavak)
        block_start, block_end = start, end
        for _ in range(8):
            ne = _extend_right_address_block(text, block_end)
            ns = _extend_left_address_block(text, block_start)
            if ne == block_end and ns == block_start:
                break
            block_end, block_start = ne, ns

        # Kiterjesztés: B épület ( előtte), ajtó (utána)
        block_start = _extend_block_left_with_address_words(text, block_start)
        block_end = _extend_block_right_with_address_words(text, block_end)

        if (block_start, block_end) in seen:
            continue
        seen.add((block_start, block_end))

        matched = text[block_start:block_end]
        # Csak ha a blokk tartalmaz cím szót, vagy rövidített kontextus (Város, Név 18-24., 2/7.)
        has_addr_in_block = _ADDRESS_BLOCK_WORDS.search(matched)
        short_block_ok = used_short_context and re.search(r"\d+[\-\d]*(?:\s*[.,]\s*\d+(?:/\d+)?\.?)?", matched)
        if not has_addr_in_block and not short_block_ok:
            continue
        results.append(
            DetectionResult(
                entity_type=EntityType.POSTAL_ADDRESS,
                matched_text=matched,
                start=block_start,
                end=block_end,
                language=language,
                source_detector="span_extender",
                confidence_score=0.80,
                risk_level=RiskClass.DIRECT_PII,
                recommended_action=RecommendedAction.REVIEW_REQUIRED,
            )
        )
    return results


def extend_adjacent_spans(text: str, detections: List[DetectionResult]) -> List[DetectionResult]:
    """
    Kiterjeszti a detekciókat: ha szám előtt/után másik szám van
    (köztes szóköz/írásjel/összekötő szó: épület, út, emelet, február stb.),
    az egész blokk egy span lesz.
    """
    result: List[DetectionResult] = []
    for d in detections:
        if not _is_extendable_type(d.entity_type):
            result.append(d)
            continue
        if not _has_digit(d.matched_text):
            result.append(d)
            continue
        start, end = d.start, d.end
        for _ in range(5):  # max 5 iteráció
            new_end = _extend_right(text, end)
            new_start = _extend_left(text, start)
            if new_end == end and new_start == start:
                break
            end, start = new_end, new_start
        new_text = text[start:end]
        if new_text != d.matched_text:
            result.append(
                DetectionResult(
                    entity_type=d.entity_type,
                    matched_text=new_text,
                    start=start,
                    end=end,
                    language=d.language,
                    source_detector=d.source_detector,
                    confidence_score=d.confidence_score,
                    risk_level=d.risk_level,
                    recommended_action=d.recommended_action,
                )
            )
        else:
            result.append(d)
    return result
