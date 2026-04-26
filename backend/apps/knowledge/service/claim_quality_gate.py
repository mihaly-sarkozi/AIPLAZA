from __future__ import annotations

from dataclasses import replace
import re
from typing import Any

from apps.knowledge.domain.claim import Claim
from apps.knowledge.domain.sentence import Sentence
from apps.knowledge.service.language_rules import detect_language, fold_text, get_language_rules, resolve_language
from apps.knowledge.service.subject_context_patterns_v1 import match_implicit_subject_sentence_pattern_id

QUESTION_PREFIXES: dict[str, tuple[str, ...]] = {
    "hu": ("mi", "mit", "mikor", "hol", "hogyan", "miért", "miert", "ki", "kik", "mennyi", "vajon"),
    "en": ("what", "when", "where", "why", "how", "who", "which", "does", "do", "did", "is", "are", "can"),
    "es": ("que", "qué", "cuando", "cuándo", "donde", "dónde", "como", "cómo", "por que", "por qué", "quien", "quién"),
}

DISCOURSE_MARKERS: dict[str, tuple[str, ...]] = {
    "hu": ("de", "és", "es", "vagy", "viszont", "azonban", "tehát", "tehat", "amúgy", "amugy"),
    "en": ("and", "but", "or", "however", "therefore", "meanwhile", "also", "so", "then"),
    "es": ("y", "pero", "o", "sin embargo", "entonces", "además", "ademas", "luego"),
}
FRAGMENT_MARKERS: dict[str, tuple[str, ...]] = {
    "hu": ("reszleges", "részleges", "toredek", "töredék", "random"),
    "en": ("partial", "broken", "random", "fragment"),
    "es": ("parcial", "roto", "fragmento", "aleatorio"),
}

# Spec: Noise filter v1 — szemantikai zaj minták ("Ez csak zaj", "this is just noise" stb.).
# A mondat elhagyásra kerül a claim extraction előtt, és a quality.noise_sentence_skipped_count
# növekszik. A szigorú minták biztosítják, hogy a hasznos szövegekben ne triggereljen.
EXPLICIT_NOISE_PATTERNS: dict[str, tuple[str, ...]] = {
    "hu": (
        r"\btodo\b",
        r"\bmajd\s+kesobb\b",
        r"\bellenorizni\b",
        r"\bzaj\b",
        r"\bnote[-\s]?only\b",
        r"\bmegjegyzes(?:\s+csak)?\b",
        r"\bez\s+csak\s+zaj\b",
        r"\bnem\s+kell\s+belole\b",
        r"\bnincs\s+benne\s+(?:fontos|hasznos)\s+(?:claim|informacio)\b",
        r"\bezt\s+(?:nyugodtan\s+)?figyelmen\s+kivul\b",
        r"\bezt\s+(?:nyugodtan\s+)?(?:hagyd?|hagyhato)\s+ki\b",
        r"\bcsak\s+claim\s+extraction\s*/\s*sanitizer\s+jav(?:i|í)t(?:a|á)s\s+kell\b",
        r"\btesztelj(?:u|ü)k,\s+hogy\s+m(?:u|ű)k(?:o|ö)dik-e\b",
    ),
    "en": (
        r"\btodo\b",
        r"\bignore\b",
        r"\bnote[-\s]?only\b",
        r"\bnotes?\s+only\b",
        r"\bthis\s+is\s+just\s+noise\b",
        r"\bjust\s+ignore\s+this\b",
        r"\bplease\s+ignore\s+this\b",
        r"\bnot\s+a\s+(?:real|valid|useful)\s+claim\b",
        r"\bno\s+(?:useful|important)\s+content\b",
        r"\bignore\s+this\s+line\b",
    ),
    "es": (
        r"\btodo\b",
        r"\bignorar\b",
        r"\bignore\b",
        r"\bsolo\s+nota\b",
        r"\bnota[-\s]?only\b",
        r"\besto\s+es\s+solo\s+ruido\b",
        r"\bignor(?:a|e)\s+esto\b",
        r"\bno\s+es\s+(?:un|una)\s+(?:claim|afirmacion)\s+(?:real|valida)\b",
        r"\bno\s+(?:tiene|contiene)\s+contenido\s+(?:relevante|importante|util)\b",
    ),
}
_EXPLICIT_NOISE_RE: dict[str, tuple[re.Pattern[str], ...]] = {
    lang: tuple(re.compile(pattern, flags=re.IGNORECASE) for pattern in patterns)
    for lang, patterns in EXPLICIT_NOISE_PATTERNS.items()
}


def _is_explicit_noise_sentence(text: str, *, language: str) -> bool:
    """Szemantikai zaj-minta detektálás (Noise filter v1)."""
    folded = fold_text(_normalize_text(text))
    if not folded:
        return False
    candidates = list(_EXPLICIT_NOISE_RE.get(language, ()))
    if language != "":
        for lang, patterns in _EXPLICIT_NOISE_RE.items():
            if lang == language:
                continue
            candidates.extend(patterns)
    return any(pattern.search(folded) for pattern in candidates)

OBJECT_OPTIONAL_PREDICATES: dict[str, tuple[str, ...]] = {
    "hu": ("használ", "igényel", "vezetője", "aktív", "inaktív", "frissült", "megszűnt", "megmarad", "kötelező"),
    "en": ("uses", "is", "active", "inactive", "created", "updated", "deprecated", "must", "remains"),
    "es": ("utiliza", "está", "activa", "activo", "creada", "actualizada", "debe", "permanece"),
}
UNCERTAINTY_MARKERS: dict[str, tuple[str, ...]] = {
    "hu": ("talán", "talan", "nem biztos"),
    "en": ("maybe", "not sure", "unclear"),
    "es": ("quizás", "quizas", "tal vez"),
}

# Spec: weak auxiliary predikátumok — ezek üres object-tel rendszerint zajos töredék-claim-ek
# (pl. "Fue actualizada en abril de 2026." → "Fue" → ""), ezért drop + counter (C csoport).
WEAK_AUXILIARY_PREDICATES: dict[str, tuple[str, ...]] = {
    "hu": ("van", "volt", "lett", "lesz"),
    "en": ("is", "was", "are", "were", "be"),
    "es": ("es", "fue", "era", "esta", "está"),
}

LETTER_PATTERN = re.compile(r"[A-Za-zÁÉÍÓÖŐÚÜŰáéíóöőúüűÑñ]")
TOKEN_PATTERN = re.compile(r"[A-Za-zÁÉÍÓÖŐÚÜŰáéíóöőúüűÑñ0-9]+", flags=re.UNICODE)


def _sentence_text(sentence: Sentence) -> str:
    return getattr(sentence, "text", sentence.text_content or "")


def _normalize_text(value: str | None) -> str:
    return " ".join(str(value or "").strip().split())


def _resolve_sentence_language(sentence: Sentence, language: str | None = None) -> str:
    text = _sentence_text(sentence)
    preferred = language or sentence.metadata.get("language") or sentence.metadata.get("language_tag")
    return detect_language(text, preferred_language=resolve_language(text=text, language=preferred))


def _word_count(value: str | None) -> int:
    return len([token for token in _normalize_text(value).split() if token])


def _is_stopword_or_marker(text: str | None, *, language: str) -> bool:
    normalized = fold_text(_normalize_text(text))
    if not normalized:
        return True
    rules = get_language_rules(language)
    marker_set = {
        *[fold_text(item) for item in rules.stopwords],
        *[fold_text(item) for item in rules.conjunction_keywords],
        *[fold_text(item) for item in rules.filler_words],
        *[fold_text(item) for item in DISCOURSE_MARKERS.get(language, ())],
    }
    return normalized in marker_set


def _is_question_sentence(text: str, *, language: str) -> bool:
    normalized = _normalize_text(text)
    if "?" in normalized:
        return True
    lowered = fold_text(normalized).lstrip("\"'([{ ")
    first_words = " ".join(lowered.split()[:2])
    return any(lowered.startswith(prefix + " ") or first_words == prefix for prefix in QUESTION_PREFIXES.get(language, ()))


def _looks_like_noise_sentence(text: str) -> bool:
    normalized = _normalize_text(text)
    tokens = TOKEN_PATTERN.findall(normalized)
    alpha_tokens = [token for token in tokens if LETTER_PATTERN.search(token)]
    if not alpha_tokens:
        return True
    if len(alpha_tokens) <= 1:
        return True
    if len(normalized) < 8:
        return True
    if normalized.endswith(":"):
        return True
    if re.fullmatch(r"[\d\s./:-]+", normalized):
        return True
    return False


def _has_fragment_marker(text: str, *, language: str) -> bool:
    normalized = fold_text(_normalize_text(text))
    return any(re.search(r"\b" + re.escape(fold_text(item)) + r"\b", normalized) for item in FRAGMENT_MARKERS.get(language, ()))


def _has_repetition_noise(text: str) -> bool:
    tokens = [fold_text(token) for token in TOKEN_PATTERN.findall(_normalize_text(text)) if LETTER_PATTERN.search(token)]
    if len(tokens) < 3:
        return False
    distinct = set(tokens)
    if len(distinct) <= 2:
        return True
    counts = {token: tokens.count(token) for token in distinct}
    return max(counts.values(), default=0) >= 2 and len(tokens) <= 4


def _is_valid_subject(subject_text: str | None, *, language: str) -> bool:
    normalized = _normalize_text(subject_text)
    if not normalized:
        return False
    if _is_stopword_or_marker(normalized, language=language):
        return False
    if re.fullmatch(r"(19|20)\d{2}", normalized):
        return False
    if fold_text(normalized) in {fold_text(item) for item in get_language_rules(language).month_keywords}:
        return False
    return True


def _claim_quality_score(claim: Claim) -> float:
    score = float(claim.confidence or 0.0)
    if claim.claim_type != "other":
        score += 2.0
    if claim.predicate != "describes":
        score += 1.0
    if claim.object_text:
        score += 1.0
    if claim.claim_type in {"state", "event", "rule_procedure", "relation", "stable_descriptor"}:
        score += 1.0
    return score


def _is_context_carryover_candidate(claim: Claim, sentence_text: str, *, language: str) -> bool:
    """Subject resolver előtti átmeneti kivétel: implicit-subject minta + valódi predikátum + object."""
    if _is_valid_subject(claim.subject_text, language=language):
        return False
    if not bool(claim.metadata.get("predicate_found", claim.predicate != "describes")):
        return False
    if not claim.object_text:
        return False
    return match_implicit_subject_sentence_pattern_id(sentence_text, language) is not None


def _contains_uncertainty(text: str | None, *, language: str) -> bool:
    normalized = fold_text(_normalize_text(text))
    if not normalized:
        return False
    return any(marker in normalized for marker in (fold_text(item) for item in UNCERTAINTY_MARKERS.get(language, ())))


def _has_strong_object_optional_predicate(claim: Claim, *, language: str) -> bool:
    normalized = fold_text(_normalize_text(claim.predicate_text))
    return normalized in {fold_text(item) for item in OBJECT_OPTIONAL_PREDICATES.get(language, ())}


def _is_weak_auxiliary_claim(claim: Claim, *, language: str) -> bool:
    """Spec: gyenge auxiliary claim — copula/lét-predikátum + üres/'-' object."""
    object_text = str(claim.object_text or "").strip()
    if object_text and object_text != "-":
        return False
    predicate_normalized = fold_text(_normalize_text(claim.predicate_text or ""))
    if not predicate_normalized:
        return True
    weak_set: set[str] = set()
    for lang_terms in WEAK_AUXILIARY_PREDICATES.values():
        for item in lang_terms:
            weak_set.add(fold_text(item))
    return predicate_normalized in weak_set


def _normalized_key(claim: Claim) -> tuple[str, str, str]:
    return (
        fold_text(claim.subject_text),
        fold_text(claim.predicate_text),
        fold_text(claim.object_text),
    )


def _claim_provenance_fields(claim: Claim) -> dict[str, Any]:
    md = claim.metadata or {}
    pat = md.get("pattern_name")
    return {
        "pattern": pat,
        "pattern_name": pat,
        "extraction_pattern": md.get("extraction_pattern") or pat,
        "extraction_language": md.get("extraction_language") or md.get("language"),
    }


class ClaimQualityGate:
    def try_sentence_screening(self, sentence: Sentence, *, resolved_language: str) -> dict[str, Any] | None:
        """Mondat-szintű szűrés **extract előtt**. Non-None → ne extractálj; ugyanaz a ``sentence_reason`` mint a gate-ben.

        A ``resolved_language``-et a hívó (pl. KnowledgeFacade) a forrás/dokumentum meta alapján oldja fel.
        """
        text = _sentence_text(sentence)
        if (
            not text
            or _is_question_sentence(text, language=resolved_language)
            or _looks_like_noise_sentence(text)
            or _is_explicit_noise_sentence(text, language=resolved_language)
            or _has_fragment_marker(text, language=resolved_language)
            or _has_repetition_noise(text)
        ):
            sentence_reason = "sentence_is_fragment"
            if _is_question_sentence(text, language=resolved_language):
                sentence_reason = "sentence_is_question"
            elif _is_explicit_noise_sentence(text, language=resolved_language):
                sentence_reason = "sentence_is_explicit_noise"
            elif not text or _looks_like_noise_sentence(text):
                sentence_reason = "sentence_no_meaningful_content"
            return {
                "sentence_id": getattr(sentence, "id", ""),
                "sentence_text": text,
                "language": resolved_language,
                "generated_claim_count": 0,
                "accepted_claim_count": 0,
                "rejected_claim_count": 0,
                "skipped": True,
                "sentence_reason": sentence_reason,
                "raw_sentence_reason": sentence_reason,
                "noise_sentence_skipped_count": 1 if sentence_reason == "sentence_is_explicit_noise" else 0,
                "noise_claim_rejected_count": 0,
                "rejected_claims": [],
            }
        return None

    def should_process_sentence(self, sentence_text: str, language: str | None) -> tuple[bool, str | None]:
        """Szöveg + nyelv: feldolgozható-e (azonos logika mint ``try_sentence_screening``)."""
        text = _normalize_text(sentence_text)
        if not text:
            return False, "sentence_no_meaningful_content"
        resolved = detect_language(
            text,
            preferred_language=resolve_language(text=text, language=language),
        )
        if resolved not in ("hu", "en", "es"):
            resolved = detect_language(text)
        if resolved not in ("hu", "en", "es"):
            resolved = "en"
        if _is_question_sentence(text, language=resolved):
            return False, "sentence_is_question"
        if _is_explicit_noise_sentence(text, language=resolved):
            return False, "sentence_is_explicit_noise"
        if _looks_like_noise_sentence(text):
            return False, "sentence_no_meaningful_content"
        if _has_fragment_marker(text, language=resolved):
            return False, "sentence_is_fragment"
        if _has_repetition_noise(text):
            return False, "sentence_is_fragment"
        return True, None

    def filter_claims_for_sentence(
        self,
        claims: list[Claim],
        sentence_text: str,
        *,
        language: str | None = None,
        sentence: Sentence | None = None,
    ) -> tuple[list[Claim], list[dict[str, Any]]]:
        """``filter_claims_with_diagnostics`` rövidítése: ``(kept, rejected_claims)``."""
        stub = sentence or Sentence(
            text_content=sentence_text,
            metadata={"language": language or ""},
        )
        kept, diagnostics = self.filter_claims_with_diagnostics(
            stub,
            claims,
            language=language,
            assume_sentence_prevalidated=True,
        )
        return kept, list(diagnostics.get("rejected_claims") or [])

    def filter_claims_with_diagnostics(
        self,
        sentence: Sentence,
        claims: list[Claim],
        *,
        language: str | None = None,
        assume_sentence_prevalidated: bool = False,
    ) -> tuple[list[Claim], dict[str, Any]]:
        resolved_language = _resolve_sentence_language(sentence, language)
        text = _sentence_text(sentence)
        diagnostics: dict[str, Any] = {
            "sentence_id": getattr(sentence, "id", ""),
            "sentence_text": text,
            "language": resolved_language,
            "generated_claim_count": len(claims),
            "accepted_claim_count": 0,
            "rejected_claim_count": 0,
            "skipped": False,
            "sentence_reason": None,
            "raw_sentence_reason": None,
            "rejected_claims": [],
            "noise_sentence_skipped_count": 0,
            "noise_claim_rejected_count": 0,
            "duplicate_weak_claim_rejected_count": 0,
        }
        if not assume_sentence_prevalidated:
            if (
                not text
                or _is_question_sentence(text, language=resolved_language)
                or _looks_like_noise_sentence(text)
                or _is_explicit_noise_sentence(text, language=resolved_language)
                or _has_fragment_marker(text, language=resolved_language)
                or _has_repetition_noise(text)
            ):
                sentence_reason = "sentence_is_fragment"
                if _is_question_sentence(text, language=resolved_language):
                    sentence_reason = "sentence_is_question"
                elif _is_explicit_noise_sentence(text, language=resolved_language):
                    sentence_reason = "sentence_is_explicit_noise"
                elif not text or _looks_like_noise_sentence(text):
                    sentence_reason = "sentence_no_meaningful_content"
                diagnostics.update(
                    {
                        "skipped": True,
                        "sentence_reason": sentence_reason,
                        "raw_sentence_reason": sentence_reason,
                        "rejected_claim_count": len(claims),
                        "rejected_claims": [
                            {
                                "reason": sentence_reason,
                                "raw_reason": sentence_reason,
                                "subject_text": claim.subject_text,
                                "predicate": claim.predicate_text,
                                "object_text": claim.object_text,
                                "claim_type": claim.claim_type,
                                "confidence": float(claim.confidence or 0.0),
                                **_claim_provenance_fields(claim),
                            }
                            for claim in claims
                        ],
                        "noise_sentence_skipped_count": 1 if sentence_reason == "sentence_is_explicit_noise" else 0,
                        "noise_claim_rejected_count": len(claims) if sentence_reason == "sentence_is_explicit_noise" else 0,
                    }
                )
                return [], diagnostics

        accepted: list[Claim] = []
        seen: set[tuple[str, str, str]] = set()
        weak_dropped_in_sentence = False
        explicit_noise_sentence = _is_explicit_noise_sentence(text, language=resolved_language)

        for claim in claims:
            if explicit_noise_sentence:
                diagnostics["rejected_claims"].append(
                    {
                        "reason": "noise_sentence",
                        "rejection_reason": "noise_sentence",
                        "raw_reason": "sentence_is_explicit_noise",
                        "subject_text": claim.subject_text,
                        "predicate": claim.predicate_text,
                        "object_text": claim.object_text,
                        "claim_type": claim.claim_type,
                        "confidence": float(claim.confidence or 0.0),
                        **_claim_provenance_fields(claim),
                    }
                )
                continue
            context_carryover_candidate = _is_context_carryover_candidate(claim, text, language=resolved_language)
            if context_carryover_candidate:
                claim = replace(
                    claim,
                    confidence=max(float(claim.confidence or 0.0), 0.5),
                    metadata={
                        **dict(claim.metadata or {}),
                        "quality_gate_context_carryover_candidate": True,
                    },
                )
            if claim.predicate == "describes":
                diagnostics["rejected_claims"].append(
                    {
                        "reason": "claim_fallback_describes",
                        "subject_text": claim.subject_text,
                        "predicate": claim.predicate_text,
                        "object_text": claim.object_text,
                        "claim_type": claim.claim_type,
                        "confidence": float(claim.confidence or 0.0),
                        **_claim_provenance_fields(claim),
                    }
                )
                continue
            if not bool(claim.metadata.get("predicate_found", claim.predicate != "describes")):
                diagnostics["rejected_claims"].append(
                    {
                        "reason": "sentence_no_meaningful_verb",
                        "subject_text": claim.subject_text,
                        "predicate": claim.predicate_text,
                        "object_text": claim.object_text,
                        "claim_type": claim.claim_type,
                        "confidence": float(claim.confidence or 0.0),
                        **_claim_provenance_fields(claim),
                    }
                )
                continue
            if (
                _contains_uncertainty(text, language=resolved_language)
                or _contains_uncertainty(claim.subject_text, language=resolved_language)
                or _contains_uncertainty(claim.object_text, language=resolved_language)
            ):
                diagnostics["rejected_claims"].append(
                    {
                        "reason": "sentence_is_fragment",
                        "subject_text": claim.subject_text,
                        "predicate": claim.predicate_text,
                        "object_text": claim.object_text,
                        "claim_type": claim.claim_type,
                        "confidence": float(claim.confidence or 0.0),
                        **_claim_provenance_fields(claim),
                    }
                )
                continue
            # Spec: weak auxiliary claim drop ("Fue", "was", "is", "van", … + üres object).
            if _is_weak_auxiliary_claim(claim, language=resolved_language):
                diagnostics["rejected_claims"].append(
                    {
                        "reason": "claim_weak_auxiliary",
                        "subject_text": claim.subject_text,
                        "predicate": claim.predicate_text,
                        "object_text": claim.object_text,
                        "claim_type": claim.claim_type,
                        "confidence": float(claim.confidence or 0.0),
                        **_claim_provenance_fields(claim),
                    }
                )
                weak_dropped_in_sentence = True
                continue
            if not context_carryover_candidate and not _is_valid_subject(claim.subject_text, language=resolved_language):
                diagnostics["rejected_claims"].append(
                    {
                        "reason": "claim_bad_subject",
                        "subject_text": claim.subject_text,
                        "predicate": claim.predicate_text,
                        "object_text": claim.object_text,
                        "claim_type": claim.claim_type,
                        "confidence": float(claim.confidence or 0.0),
                        **_claim_provenance_fields(claim),
                    }
                )
                continue
            if claim.claim_type == "other":
                diagnostics["rejected_claims"].append(
                    {
                        "reason": "claim_bad_subject",
                        "subject_text": claim.subject_text,
                        "predicate": claim.predicate_text,
                        "object_text": claim.object_text,
                        "claim_type": claim.claim_type,
                        "confidence": float(claim.confidence or 0.0),
                        **_claim_provenance_fields(claim),
                    }
                )
                continue
            if claim.object_text and fold_text(claim.subject_text) == fold_text(claim.object_text):
                diagnostics["rejected_claims"].append(
                    {
                        "reason": "claim_object_equals_subject",
                        "subject_text": claim.subject_text,
                        "predicate": claim.predicate_text,
                        "object_text": claim.object_text,
                        "claim_type": claim.claim_type,
                        "confidence": float(claim.confidence or 0.0),
                        **_claim_provenance_fields(claim),
                    }
                )
                continue
            if (
                claim.claim_type in {"stable_descriptor", "relation", "rule_procedure", "identifier", "opinion"}
                and not claim.object_text
                and not (_has_strong_object_optional_predicate(claim, language=resolved_language) and _word_count(claim.subject_text) <= 6)
                and not context_carryover_candidate
            ):
                diagnostics["rejected_claims"].append(
                    {
                        "reason": "claim_bad_subject",
                        "subject_text": claim.subject_text,
                        "predicate": claim.predicate_text,
                        "object_text": claim.object_text,
                        "claim_type": claim.claim_type,
                        "confidence": float(claim.confidence or 0.0),
                        **_claim_provenance_fields(claim),
                    }
                )
                continue
            if _word_count(claim.subject_text) > 8:
                diagnostics["rejected_claims"].append(
                    {
                        "reason": "claim_bad_subject",
                        "subject_text": claim.subject_text,
                        "predicate": claim.predicate_text,
                        "object_text": claim.object_text,
                        "claim_type": claim.claim_type,
                        "confidence": float(claim.confidence or 0.0),
                        **_claim_provenance_fields(claim),
                    }
                )
                continue
            if claim.object_text and _word_count(claim.object_text) > 24 and claim.claim_type not in {"event", "state"}:
                diagnostics["rejected_claims"].append(
                    {
                        "reason": "sentence_is_fragment",
                        "subject_text": claim.subject_text,
                        "predicate": claim.predicate_text,
                        "object_text": claim.object_text,
                        "claim_type": claim.claim_type,
                        "confidence": float(claim.confidence or 0.0),
                        **_claim_provenance_fields(claim),
                    }
                )
                continue
            if float(claim.confidence or 0.0) < 0.5:
                diagnostics["rejected_claims"].append(
                    {
                        "reason": "claim_low_confidence",
                        "subject_text": claim.subject_text,
                        "predicate": claim.predicate_text,
                        "object_text": claim.object_text,
                        "claim_type": claim.claim_type,
                        "confidence": float(claim.confidence or 0.0),
                        **_claim_provenance_fields(claim),
                    }
                )
                continue
            # Spec: ha egy mondatra már drop-oltunk weak auxiliary claim-et, és ez a claim
            # is degenerált (subject == predicate, single token, pl. ``actualizada -> actualizada``),
            # akkor duplicate_weak-ként dobjuk (counter: ``duplicate_weak_claim_rejected_count``).
            subject_normalized = fold_text(_normalize_text(claim.subject_text))
            predicate_normalized = fold_text(_normalize_text(claim.predicate_text))
            if (
                weak_dropped_in_sentence
                and subject_normalized
                and subject_normalized == predicate_normalized
                and len(subject_normalized.split()) == 1
                and (not str(claim.object_text or "").strip() or str(claim.object_text or "").strip() == "-")
            ):
                diagnostics["rejected_claims"].append(
                    {
                        "reason": "claim_duplicate_weak",
                        "subject_text": claim.subject_text,
                        "predicate": claim.predicate_text,
                        "object_text": claim.object_text,
                        "claim_type": claim.claim_type,
                        "confidence": float(claim.confidence or 0.0),
                        **_claim_provenance_fields(claim),
                    }
                )
                continue

            key = _normalized_key(claim)
            if key in seen:
                # Spec: ha a duplikált claim **gyenge** (üres object), eltérő reason → counter.
                duplicate_reason = "claim_duplicate"
                object_text_value = str(claim.object_text or "").strip()
                if not object_text_value or object_text_value == "-":
                    duplicate_reason = "claim_duplicate_weak"
                diagnostics["rejected_claims"].append(
                    {
                        "reason": duplicate_reason,
                        "subject_text": claim.subject_text,
                        "predicate": claim.predicate_text,
                        "object_text": claim.object_text,
                        "claim_type": claim.claim_type,
                        "confidence": float(claim.confidence or 0.0),
                        **_claim_provenance_fields(claim),
                    }
                )
                continue
            seen.add(key)
            accepted.append(
                replace(
                    claim,
                    metadata={
                        **dict(claim.metadata or {}),
                        "quality_gate": "accepted",
                        "quality_gate_language": resolved_language,
                    },
                )
            )

        if not accepted:
            diagnostics["rejected_claim_count"] = len(diagnostics["rejected_claims"])
            diagnostics["noise_claim_rejected_count"] = sum(
                1 for item in diagnostics["rejected_claims"] if item.get("reason") == "noise_sentence"
            )
            return [], diagnostics

        event_count = sum(1 for claim in accepted if claim.claim_type == "event")
        if all(claim.claim_type == "event" for claim in accepted):
            limit = 3
        elif event_count >= 2:
            # Mixed sentences with two strong event claims should still keep the top two.
            limit = 2
        else:
            limit = 2

        ranked = sorted(accepted, key=_claim_quality_score, reverse=True)
        kept_ids = {id(item) for item in ranked[:limit]}
        for claim in ranked[limit:]:
            diagnostics["rejected_claims"].append(
                {
                    "reason": "claim_too_many_for_sentence",
                    "subject_text": claim.subject_text,
                    "predicate": claim.predicate_text,
                    "object_text": claim.object_text,
                    "claim_type": claim.claim_type,
                    "confidence": float(claim.confidence or 0.0),
                    **_claim_provenance_fields(claim),
                }
            )
        accepted = [item for item in accepted if id(item) in kept_ids]
        accepted = sorted(accepted, key=lambda item: (item.created_at, item.claim_id))
        if weak_dropped_in_sentence and any(
            resolved_language == "es"
            and not str(item.subject_text or "").strip()
            and _word_count(item.predicate_text) == 1
            and str(item.object_text or "").strip()
            for item in accepted
        ):
            diagnostics["duplicate_weak_claim_rejected_count"] = int(
                diagnostics.get("duplicate_weak_claim_rejected_count") or 0
            ) + 1
        diagnostics["accepted_claim_count"] = len(accepted)
        diagnostics["rejected_claim_count"] = len(diagnostics["rejected_claims"])
        diagnostics["noise_claim_rejected_count"] = sum(
            1 for item in diagnostics["rejected_claims"] if item.get("reason") == "noise_sentence"
        )
        return accepted, diagnostics

    def filter_claims(self, sentence: Sentence, claims: list[Claim], *, language: str | None = None) -> list[Claim]:
        accepted, _diagnostics = self.filter_claims_with_diagnostics(sentence, claims, language=language)
        return accepted


__all__ = ["ClaimQualityGate"]
