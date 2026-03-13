# apps/knowledge/pii/pipeline.py
"""
Presidio központú PII pipeline: nyelvdetektálás → analyze → policy szűrés → (start, end, type, value).
Ha a Presidio nem elérhető (pl. nincs spacy), legacy regex réteg fut.
"""
from __future__ import annotations

import re
from typing import List, Tuple

from apps.knowledge.pii.policy import filter_by_policy, map_entity_type, entities_for_sensitivity
from apps.knowledge.pii.nlp_setup import get_analyzer_for_language

# PiiMatch: (start, end, data_type, value)
PiiMatch = Tuple[int, int, str, str]


def _detect_language(text: str) -> str:
    """Nyelvdetektálás: en, hu, es vagy fallback en."""
    if not text or not text.strip():
        return "en"
    try:
        import langdetect
        lang = langdetect.detect(text)
        if lang in ("hu", "es"):
            return lang
        return "en"
    except Exception:
        return "en"


# --- Legacy regex réteg (ugyanazok a minták, Presidio nélkül) ---
# Névminta: két nagybetűvel kezdődő szó (magyar/angol), pl. Kovács János, John Smith
_LEGACY_NAME_PATTERN = (
    r"\b[A-ZÁÉÍÓÖÜŐÚ][a-záéíóöüőú]+\s+[A-ZÁÉÍÓÖÜŐÚ][a-záéíóöüőú]+\b"
    r"|\b[A-Z][a-z]+\s+[A-Z][a-z]+\b"
)
# Cím: HU irányítószám + város + , + utca/tér stb. + házszám (pl. 1123 Budapest, Alkotás utca 15.)
# vagy általános: város, utca név szám / street name number
_LEGACY_ADDRESS_HU = (
    r"\b\d{4}\s+[A-ZÁÉÍÓÖÜŐÚ][a-záéíóöüőú]+(?:\s+[A-Za-záéíóöüőú]+)*\s*,\s*"
    r"[A-ZÁÉÍÓÖÜŐÚa-záéíóöüőú][^,]*?\s+\d+[a-z]?\s*\.?"
)
_LEGACY_ADDRESS_GENERIC = (
    r"\b(?:lakcím|cím|address|addr\.?)\s*:\s*[^.\n]{10,80}\d+[a-z]?\s*\.?"
)
_LEGACY_PATTERNS: List[Tuple[str, str]] = [
    ("email", r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    ("telefonszám", r"\b(?:\+36|06)[\s\-/]?\d{1,2}[\s\-/]?\d{3}[\s\-/]?\d{4}\b"),
    ("telefonszám", r"\b\d{2}[\s\-/]\d{3}[\s\-/]\d{4}\b"),
    ("telefonszám", r"\+\d{1,3}[\s\-]?(?:\d[\s\-]?){8,14}\d\b"),
    ("iban", r"\b[A-Z]{2}\d{2}\s?(?:[A-Z0-9]\s?){4}(?:[A-Z0-9]\s?){4,28}\b"),
    ("rendszám", r"\b[A-Z]{3}[- ]?\d{3}\b"),
    ("rendszám", r"\b[A-Z]{2}[- ]?\d{2}[- ]?[A-Z]{2}[- ]?\d{2}\b"),
    ("ügyfélazonosító", r"\b(?:UGY|UGYFEL|CLIENT)[\- ]?\d{4,10}\b"),
    ("ügyfélazonosító", r"#\d{4,12}\b"),
    ("szerződésszám", r"\b(?:SZ|Szerz\.?|Szerződés)[\- ]?\d{4,12}\b"),
    ("ticket_id", r"\b(?:TKT|TICKET|JIRA)[\- ]?\d{4,10}\b"),
    # Dátum: ISO, EU, és születési dátum szóközös forma (1992. 03. 14. / 14. 03. 1992.)
    ("dátum", r"\b(?:19|20)\d{2}[.\-/](?:0[1-9]|1[0-2])[.\-/](?:0[1-9]|[12]\d|3[01])\b"),
    ("dátum", r"\b(?:0[1-9]|[12]\d|3[01])[.\-/](?:0[1-9]|1[0-2])[.\-/](?:19|20)\d{2}\b"),
    ("dátum", r"\b(?:19|20)\d{2}\.\s*(?:0[1-9]|1[0-2])\.\s*(?:0[1-9]|[12]\d|3[01])\.?"),
    ("dátum", r"\b(?:0[1-9]|[12]\d|3[01])\.\s*(?:0[1-9]|1[0-2])\.\s*(?:19|20)\d{2}\.?"),
    # Születési dátum kontextussal: "Született: 1992. 03. 14." vagy "dob: 14/03/1992"
    ("dátum", r"(?i)\b(?:született|szül\.?|date of birth|dob)\s*:\s*(?:19|20)\d{2}[.\s\-/]*(?:0[1-9]|1[0-2])[.\s\-/]*(?:0[1-9]|[12]\d|3[01])\b"),
    ("dátum", r"(?i)\b(?:született|szül\.?|date of birth|dob)\s*:\s*(?:0[1-9]|[12]\d|3[01])[.\s\-/]*(?:0[1-9]|1[0-2])[.\s\-/]*(?:19|20)\d{2}\b"),
    ("név", _LEGACY_NAME_PATTERN),
    ("cím", _LEGACY_ADDRESS_HU),
    ("cím", _LEGACY_ADDRESS_GENERIC),
]


def _filter_pii_legacy(text: str, sensitivity: str) -> List[PiiMatch]:
    """Regex alapú felismerés Presidio nélkül (ugyanazok az entitástípusok)."""
    if not text or not text.strip():
        return []
    collected: List[PiiMatch] = []
    for entity_type, pattern in _LEGACY_PATTERNS:
        if not filter_by_policy(entity_type, sensitivity):
            continue
        for m in re.finditer(pattern, text):
            val = m.group(0).strip()
            if val:
                collected.append((m.start(), m.end(), entity_type, val))
    collected.sort(key=lambda x: (x[0], -x[1]))
    seen: List[Tuple[int, int]] = []
    merged: List[PiiMatch] = []
    for start, end, dtype, val in collected:
        if any(s < end and e > start for s, e in seen):
            continue
        seen.append((start, end))
        merged.append((start, end, dtype, val))
    return merged


def filter_pii(text: str, sensitivity: str) -> List[PiiMatch]:
    """
    Presidio (spaCy en/es + Stanza hu) + egyéni recognizerek + policy;
    ha az NLP modellek nincsenek, legacy regex.
    Visszaadja: [(start, end, data_type, value), ...].
    """
    if not text or not text.strip():
        return []

    lang = _detect_language(text)
    # hu → Stanza analyzer, en/es → spaCy analyzer
    try:
        analyzer = get_analyzer_for_language(lang)
    except Exception:
        analyzer = None
    if analyzer is not None:
        try:
            # Presidio en/es analyzer csak "en" vagy "es"-t fogad, hu analyzer "hu"-t
            analyze_lang = lang if lang in ("es", "hu") else "en"
            results = analyzer.analyze(text=text, language=analyze_lang)
            collected: List[PiiMatch] = []
            for r in results:
                # NER típusok (PERSON, ORG, stb.) → név, szervezet, hely
                dtype = map_entity_type(r.entity_type)
                if not filter_by_policy(dtype, sensitivity):
                    continue
                start, end = r.start, r.end
                value = text[start:end] if 0 <= start < end <= len(text) else ""
                if value.strip():
                    collected.append((start, end, dtype, value))
            collected.sort(key=lambda x: (x[0], -x[1]))
            seen: List[Tuple[int, int]] = []
            merged: List[PiiMatch] = []
            for start, end, dtype, val in collected:
                if any(s < end and e > start for s, e in seen):
                    continue
                seen.append((start, end))
                merged.append((start, end, dtype, val))
            allowed = entities_for_sensitivity(sensitivity)
            # Név fallback: NER nem mindig ad PERSON-t (pl. Stanza hu), legacy két szós minta kiegészít
            if "név" in allowed:
                for m in re.finditer(_LEGACY_NAME_PATTERN, text):
                    start, end = m.start(), m.end()
                    if any(s < end and e > start for s, e in seen):
                        continue
                    val = m.group(0).strip()
                    if val:
                        seen.append((start, end))
                        merged.append((start, end, "név", val))
            # Cím fallback: NER nem ad teljes címet, legacy irányítószám + város + utca minta
            if "cím" in allowed:
                for pattern in (_LEGACY_ADDRESS_HU, _LEGACY_ADDRESS_GENERIC):
                    for m in re.finditer(pattern, text):
                        start, end = m.start(), m.end()
                        if any(s < end and e > start for s, e in seen):
                            continue
                        val = m.group(0).strip()
                        if val and len(val) > 5:
                            seen.append((start, end))
                            merged.append((start, end, "cím", val))
            merged.sort(key=lambda x: (x[0], -x[1]))
            return merged
        except Exception:
            pass

    return _filter_pii_legacy(text, sensitivity)


def apply_pii_replacements(
    text: str,
    matches: List[PiiMatch],
    ref_id_by_index: List[str],
) -> str:
    """
    A szövegben a matches szerinti tartományokat helyettesíti [típus_ref_id]-vel.
    ref_id_by_index[i] a matches[i]-hez tartozó ref_id (a tárolás után kapott).
    """
    if not matches or len(ref_id_by_index) != len(matches):
        return text
    result = text
    for i in range(len(matches) - 1, -1, -1):
        start, end, dtype, _ = matches[i]
        ref_id = ref_id_by_index[i]
        result = result[:start] + f"[{dtype}_{ref_id}]" + result[end:]
    return result
