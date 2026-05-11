# Ez a fájl a(z) ner_detector modul backend logikáját tartalmazza.
"""
NER-based detector using spaCy (en, es) or Stanza (hu).
Degrades gracefully if models are not installed.
"""
from __future__ import annotations

import re
from typing import List, Optional

from apps.knowledge.pii_gdpr.enums import EntityType, RiskClass, RecommendedAction
from apps.knowledge.pii_gdpr.models import DetectionResult
from apps.knowledge.pii_gdpr.detectors.base import BaseDetector

# Szavak, amiket a NER ne detektáljon névként (pl. role-based, role)
_PERSON_NAME_BLOCKLIST = frozenset({"role", "role-based", "role based", "rolebased"})
_PERSON_SUFFIX_PATTERN = re.compile(
    r"\s+(?:"
    r"útlev[ée]lsz[aá]ma|"
    r"útlev[ée]l|"
    r"passport(?:\s+number)?|"
    r"szem[eé]lyi(?:\s+igazolv[aá]ny)?(?:\s+sz[aá]ma)?|"
    r"igazolv[aá]ny(?:\s+sz[aá]ma)?"
    r")\b.*$",
    re.IGNORECASE,
)

# NER label -> our EntityType
_LABEL_MAP = {
    "PERSON": EntityType.PERSON_NAME,
    "PER": EntityType.PERSON_NAME,
    "ORG": EntityType.UNKNOWN,  # policy can allow org names
    "ORGANIZATION": EntityType.UNKNOWN,
    "GPE": EntityType.UNKNOWN,
    "LOC": EntityType.UNKNOWN,
    "LOCATION": EntityType.UNKNOWN,
    "DATE": EntityType.DATE,  # NER nem különböztet meg születési dátumot → általános dátum
}


def _normalize_person_span(text: str, start: int, end: int) -> tuple[int, int, str] | None:
    raw = text[start:end]
    stripped = raw.strip()
    if not stripped:
        return None

    leading_ws = len(raw) - len(raw.lstrip())
    normalized_start = start + leading_ws
    normalized_end = normalized_start + len(stripped)
    cleaned = _PERSON_SUFFIX_PATTERN.sub("", stripped).strip()
    if not cleaned:
        return None

    mt = cleaned.casefold()
    if mt in _PERSON_NAME_BLOCKLIST or any(mt.startswith(b) for b in ("role-", "role ")):
        return None

    if cleaned != stripped:
        normalized_end = normalized_start + len(cleaned)
    return normalized_start, normalized_end, cleaned


class NERDetector(BaseDetector):
    """Uses spaCy or Stanza for NER. Reports unavailable if no model loaded."""

    name = "ner"
    _nlp_en: Optional[object] = None
    _nlp_es: Optional[object] = None
    _nlp_hu: Optional[object] = None
    _load_attempted = False

    # Ez a metódus biztosítja a(z) loaded logikáját.
    @classmethod
    def _ensure_loaded(cls) -> None:
        if cls._load_attempted:
            return
        cls._load_attempted = True
        try:
            import spacy
            try:
                cls._nlp_en = spacy.load("en_core_web_sm")
            except OSError:
                pass
            try:
                cls._nlp_es = spacy.load("es_core_news_sm")
            except OSError:
                pass
        except ImportError:
            pass
        try:
            import stanza
            try:
                cls._nlp_hu = stanza.Pipeline("hu", processors="tokenize,ner", use_gpu=False, verbose=False)
            except Exception:
                pass
        except ImportError:
            pass

    # Ez a metódus a(z) available logikáját valósítja meg.
    def available(self) -> bool:
        self._ensure_loaded()
        return self._nlp_en is not None or self._nlp_es is not None or self._nlp_hu is not None

    # Ez a metódus a(z) detect_spacy logikáját valósítja meg.
    def _detect_spacy(self, text: str, nlp: object, language: str) -> List[DetectionResult]:
        results: List[DetectionResult] = []
        doc = nlp(text[:1_000_000])
        for ent in getattr(doc, "ents", []):
            label = ent.label_
            entity_type = _LABEL_MAP.get(label, EntityType.UNKNOWN)
            if entity_type == EntityType.UNKNOWN and label not in ("ORG", "GPE", "LOC", "ORGANIZATION", "LOCATION"):
                continue
            if entity_type == EntityType.UNKNOWN:
                continue
            start = ent.start_char
            end = ent.end_char
            matched_text = text[start:end]
            if entity_type == EntityType.PERSON_NAME:
                normalized = _normalize_person_span(text, start, end)
                if normalized is None:
                    continue
                start, end, matched_text = normalized
            confidence = 0.78
            risk = RiskClass.DIRECT_PII if entity_type == EntityType.PERSON_NAME else RiskClass.INDIRECT_IDENTIFIER
            results.append(
                DetectionResult(
                    entity_type=entity_type,
                    matched_text=matched_text,
                    start=start,
                    end=end,
                    language=language,
                    source_detector=self.name,
                    confidence_score=confidence,
                    risk_level=risk,
                    recommended_action=RecommendedAction.REVIEW_REQUIRED,
                )
            )
        return results

    # Ez a metódus a(z) detect_stanza logikáját valósítja meg.
    def _detect_stanza(self, text: str, language: str) -> List[DetectionResult]:
        results: List[DetectionResult] = []
        if self._nlp_hu is None:
            return results
        doc = self._nlp_hu(text[:1_000_000])
        for ent in getattr(doc, "entities", []):
            label = getattr(ent, "type", "O")
            entity_type = _LABEL_MAP.get(label, EntityType.UNKNOWN)
            if entity_type == EntityType.UNKNOWN:
                continue
            start = getattr(ent, "start_char", 0)
            end = getattr(ent, "end_char", 0)
            if end <= start:
                continue
            matched = text[start:end]
            if entity_type == EntityType.PERSON_NAME:
                normalized = _normalize_person_span(text, start, end)
                if normalized is None:
                    continue
                start, end, matched = normalized
            confidence = 0.76
            risk = RiskClass.DIRECT_PII if entity_type == EntityType.PERSON_NAME else RiskClass.INDIRECT_IDENTIFIER
            results.append(
                DetectionResult(
                    entity_type=entity_type,
                    matched_text=matched,
                    start=start,
                    end=end,
                    language=language,
                    source_detector=self.name,
                    confidence_score=confidence,
                    risk_level=risk,
                    recommended_action=RecommendedAction.REVIEW_REQUIRED,
                )
            )
        return results

    # Ez a metódus a(z) detect logikáját valósítja meg.
    def detect(self, text: str, language: str = "en") -> List[DetectionResult]:
        self._ensure_loaded()
        if language == "hu" and self._nlp_hu is not None:
            return self._detect_stanza(text, language)
        if language == "es" and self._nlp_es is not None:
            return self._detect_spacy(text, self._nlp_es, language)
        if self._nlp_en is not None:
            return self._detect_spacy(text, self._nlp_en, language if language == "en" else "en")
        return []
