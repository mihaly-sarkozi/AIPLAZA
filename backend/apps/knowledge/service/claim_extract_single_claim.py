"""ClaimExtractorV1: egy predikátumhoz egy Claim összeállítása."""
from __future__ import annotations

import re

from apps.knowledge.domain.claim import Claim
from apps.knowledge.domain.mention import Mention
from apps.knowledge.domain.sentence import Sentence
from apps.knowledge.service.claim_extract_constants import USE_PREDICATE_FOLDS
from apps.knowledge.service.claim_extract_hu_use import hu_find_best_use_head_span, hu_hasznal_use_subject_end_char
from apps.knowledge.service.claim_extract_mentions import (
    find_best_mention_id,
    select_subject_mention,
    select_use_subject_mention,
)
from apps.knowledge.service.claim_extract_normalize import normalize_predicate, word_count
from apps.knowledge.service.claim_extract_object_build import build_object_text, fallback_subject
from apps.knowledge.service.claim_extract_text_clean import (
    build_claim_text,
    clean_object_slice,
    clean_subject_slice,
    is_valid_subject_text,
    normalize_predicate_display,
    should_drop_state_object,
    trim_hu_felelt_leading_subject,
    trim_hu_vezetoje_leading_subject,
)
from apps.knowledge.service.claim_extraction_provenance import attach_extraction_provenance, infer_extraction_pattern_name
from apps.knowledge.service.claim_typing import apply_claim_type_config, guess_claim_type
from apps.knowledge.service.claim_sanitizer import subject_sanitizer_tags
from apps.knowledge.service.language_rules import fold_text


_HU_CAPITALIZED_TOKEN = r"[A-ZÁÉÍÓÖŐÚÜŰ][\wÁÉÍÓÖŐÚÜŰáéíóöőúüű\-]+"
_HU_FELELT_PREPREDICATE_RE = re.compile(
    rf"^\s*(?P<subject>{_HU_CAPITALIZED_TOKEN}(?:\s+{_HU_CAPITALIZED_TOKEN}){{1,3}})\s+"
    r"(?:(?P<year>(?:19|20)\d{2})-?(?:ben|ban)\s+)?"
    r"(?:még\s+)?(?:a|az)?\s*(?P<object>.+?\b[\w\-]+ért)\s*$",
    flags=re.UNICODE,
)
_HU_IGENYEL_PREPREDICATE_RE = re.compile(
    r"^\s*(?P<subject>(?:a|az)?\s*.+?\b(?:rendszer|modul|szoftver|feature|product|system))\s+"
    r"(?:jelenleg\s+)?(?P<object>.+?)\s*$",
    flags=re.IGNORECASE | re.UNICODE,
)
# Spec: "X jelenleg Y rendszert / Y-t" típusú HU subject — pl. "billing service jelenleg
# Stripe rendszert". A subject = "billing service" ("jelenleg" előtti szegmens), object = a
# "használ" predicate utáni rész. Ez a "hasznal*" családra is alkalmazandó (igenyel
# jelenleg csak `igényel`-re fut), különben a teljes kifejezés egy hosszú subject-be ragad.
_HU_HASZNAL_CURRENT_SUBJECT_RE = re.compile(
    r"^\s*(?:a|az)\s+(?P<subject>[^,;.]+?)\s+jelenleg\s+.+$",
    flags=re.IGNORECASE | re.UNICODE,
)
_HU_FELELT_CONTEXT_TRIGGER_RE = re.compile(
    r"\b(korábban|korabban|előtte|elotte|később|kesobb|akkoriban)\b",
    flags=re.IGNORECASE | re.UNICODE,
)
_HU_MEGSZUNT_YEAR_RE = re.compile(
    r"^\s*(?P<subject>.+?)\s+(?P<year>(?:19|20)\d{2}(?:-?ben|-?ban)?)\s*$",
    flags=re.IGNORECASE | re.UNICODE,
)


def _extract_hu_felelt_subject_object(text: str, predicate_idx: int | None) -> tuple[str, str] | None:
    if predicate_idx is None:
        return None
    head = text[:predicate_idx].strip(" ,;:-.")
    temporal_match = _HU_FELELT_CONTEXT_TRIGGER_RE.search(head)
    if temporal_match is not None:
        subject_match = re.match(rf"^\s*(?P<subject>{_HU_CAPITALIZED_TOKEN}(?:\s+{_HU_CAPITALIZED_TOKEN}){{1,3}})\b", head)
        object_part = head[temporal_match.end() :].strip(" ,;:-.")
        object_part = re.sub(r"^(?:még\s+)?(?:a|az)\s+", "", object_part, flags=re.IGNORECASE).strip(" ,;:-.")
        if object_part:
            obj = clean_object_slice(object_part, language="hu")
            if subject_match is None:
                return "", obj
            subject = clean_subject_slice(subject_match.group("subject"), language="hu")
            if subject and obj and fold_text(subject) != fold_text(obj):
                return subject, obj
    match = _HU_FELELT_PREPREDICATE_RE.match(head)
    if match is None:
        return None
    subject = clean_subject_slice(match.group("subject"), language="hu")
    obj = clean_object_slice(match.group("object"), language="hu")
    if not subject or not obj or fold_text(subject) == fold_text(obj):
        return None
    return subject, obj


def _extract_hu_igenyel_subject_object(text: str, predicate_idx: int | None) -> tuple[str, str] | None:
    if predicate_idx is None:
        return None
    head = text[:predicate_idx].strip(" ,;:-.")
    match = _HU_IGENYEL_PREPREDICATE_RE.match(head)
    if match is None:
        return None
    subject = clean_subject_slice(match.group("subject"), language="hu")
    obj = clean_object_slice(match.group("object"), language="hu")
    if not subject or not obj or fold_text(subject) == fold_text(obj):
        return None
    return subject, obj


def _extract_hu_current_state_subject(text: str, predicate_idx: int | None) -> str | None:
    """HU "X jelenleg ..." minta — subject = "X" (a "jelenleg" előtti szegmens, cikk nélkül)."""
    if predicate_idx is None:
        return None
    head = text[:predicate_idx]
    match = _HU_HASZNAL_CURRENT_SUBJECT_RE.match(head)
    if match is None:
        return None
    subject = clean_subject_slice(match.group("subject"), language="hu")
    return subject or None


def _extract_hu_megszunt_subject_object(text: str, predicate_idx: int | None) -> tuple[str, str] | None:
    if predicate_idx is None:
        return None
    head = text[:predicate_idx].strip(" ,;:-.")
    match = _HU_MEGSZUNT_YEAR_RE.match(head)
    if match is None:
        return None
    subject = clean_subject_slice(match.group("subject"), language="hu")
    obj = clean_object_slice(match.group("year"), language="hu")
    if not subject or not obj:
        return None
    return subject, obj


def _split_hu_felelose_title_predicate(predicate: str, object_text: str | None) -> tuple[str, str | None]:
    """Nagy Eszter --adatvédelmi felelőse--> Zalka 2000 típusú title relation finomítás."""
    if normalize_predicate(predicate) != "felelose" or not object_text:
        return predicate, object_text
    tokens = object_text.split()
    if len(tokens) < 3:
        return predicate, object_text
    title_prefix = tokens[-1]
    base_object = " ".join(tokens[:-1]).strip()
    if not base_object:
        return predicate, object_text
    return f"{title_prefix} {predicate}", base_object


def _split_en_role_at_org(
    predicate: str,
    object_text: str | None,
    subject_text: str | None,
) -> tuple[str, str] | None:
    """Compat helper: `is` + `role at ORG` -> `role at`, `ORG`."""
    if normalize_predicate(predicate) != "is" or not object_text:
        return None
    match = re.match(
        r"^\s*(?:the\s+)?(?P<role>.+?)\s+at\s+(?P<org>.+?)\s*$",
        object_text,
        flags=re.IGNORECASE | re.UNICODE,
    )
    if match is None:
        return None
    role = clean_subject_slice(match.group("role"), language="en")
    org = clean_object_slice(match.group("org"), language="en")
    if not role or not org:
        return None
    if subject_text and fold_text(org) == fold_text(subject_text):
        return None
    return f"{role} at", org


def _strip_source_phrase_prefix(text: str | None, *, language: str) -> str:
    value = str(text or "").strip()
    if not value:
        return value
    patterns = {
        "en": (
            r"^(?:according to the document|according to the source|the document says|document says|the report states that|report states that|the report states|report states)\b[\s,;:.-]*",
        ),
        "hu": (
            r"^(?:a dokumentum szerint|dokumentum szerint|a forrás szerint|a forras szerint|forrás szerint|forras szerint)\b[\s,;:.-]*",
        ),
        "es": (
            r"^(?:según el documento|segun el documento|según la fuente|segun la fuente|el documento indica)\b[\s,;:.-]*",
        ),
    }
    for pattern in patterns.get(language, ()):
        updated = re.sub(pattern, "", value, count=1, flags=re.IGNORECASE | re.UNICODE).strip(" ,;:-.")
        if updated != value:
            return updated
    return value


def _split_es_role_en_org(
    predicate: str,
    object_text: str | None,
    subject_text: str | None,
) -> tuple[str, str] | None:
    """Compat helper: `es` + `responsable ... en ORG` -> `responsable ... en`, `ORG`."""
    if normalize_predicate(predicate) != "es" or not object_text:
        return None
    match = re.match(
        r"^\s*(?P<role>.+?)\s+en\s+(?P<org>.+?)\s*$",
        object_text,
        flags=re.IGNORECASE | re.UNICODE,
    )
    if match is None:
        return None
    role = clean_subject_slice(match.group("role"), language="es")
    org = clean_object_slice(match.group("org"), language="es")
    if not role or not org:
        return None
    if subject_text and fold_text(org) == fold_text(subject_text):
        return None
    return f"{role} en", org


def build_claim(
    sentence: Sentence,
    *,
    mentions: list[Mention],
    text: str,
    predicate: str,
    predicate_idx: int | None,
    predicate_end_idx: int | None,
    next_predicate_idx: int | None,
    language: str,
    inherited_subject: str | None = None,
) -> Claim | None:
    raw_predicate = predicate
    pred_f = normalize_predicate(raw_predicate)
    subject_mention = select_subject_mention(mentions, predicate_idx=predicate_idx, language=language)
    use_head_phrase: str | None = None
    use_head_end_idx: int | None = None
    if pred_f in USE_PREDICATE_FOLDS.get(language, set()):
        use_mention = select_use_subject_mention(mentions, predicate_idx=predicate_idx, language=language)
        if use_mention is not None:
            subject_mention = use_mention
        elif language == "hu" and predicate_idx is not None:
            span = hu_find_best_use_head_span(text[:predicate_idx])
            if span:
                use_head_phrase, use_head_end_idx = span
                subject_mention = None
    if subject_mention is not None:
        raw_subject_text = subject_mention.surface_text
        subject_text = clean_subject_slice(raw_subject_text, language=language)
        subject_source = "mention"
    else:
        raw_subject_text = text[:predicate_idx].strip(" ,;:-.") if predicate_idx is not None else fallback_subject(text, predicate_idx, language=language)
        subject_text = clean_subject_slice(_strip_source_phrase_prefix(raw_subject_text, language=language), language=language)
        subject_source = "fallback"
    if use_head_phrase:
        raw_subject_text = use_head_phrase
        subject_text = clean_subject_slice(raw_subject_text, language=language)
        subject_source = "hu_use_head_heuristic"
    if word_count(subject_text) > 5 and use_head_phrase is None:
        best_subject_mention = select_subject_mention(mentions, predicate_idx=predicate_idx, language=language)
        if pred_f in USE_PREDICATE_FOLDS.get(language, set()):
            use_best = select_use_subject_mention(mentions, predicate_idx=predicate_idx, language=language)
            if use_best is not None:
                best_subject_mention = use_best
        if best_subject_mention is not None:
            subject_mention = best_subject_mention
            raw_subject_text = best_subject_mention.surface_text
            subject_text = clean_subject_slice(raw_subject_text, language=language)
            subject_source = "long_subject_rewrite"
    suppress_inherited_subject = False
    if language == "hu" and pred_f == "vezetoje":
        subject_text = trim_hu_vezetoje_leading_subject(subject_text)
    if language == "hu" and pred_f == "felelt":
        felelt_override = _extract_hu_felelt_subject_object(text, predicate_idx)
        if felelt_override is not None:
            subject_text, _ = felelt_override
            raw_subject_text = subject_text
            subject_mention = None
            if subject_text:
                subject_source = "hu_felelt_time_subject_pattern"
            else:
                subject_source = "implicit_subject_candidate"
                suppress_inherited_subject = True
        subject_text = trim_hu_felelt_leading_subject(subject_text)
    hu_object_override: str | None = None
    if language == "hu" and pred_f == "igenyel":
        igenyel_override = _extract_hu_igenyel_subject_object(text, predicate_idx)
        if igenyel_override is not None:
            subject_text, hu_object_override = igenyel_override
            raw_subject_text = subject_text
            subject_mention = None
            subject_source = "hu_igenyel_current_system_pattern"
    if language == "hu" and pred_f in {"hasznal", "hasznalja", "hasznalnia"}:
        current_subject = _extract_hu_current_state_subject(text, predicate_idx)
        if current_subject and (
            word_count(subject_text) > word_count(current_subject)
            or fold_text(current_subject) != fold_text(subject_text)
        ):
            if word_count(current_subject) >= 1 and word_count(current_subject) <= 4:
                subject_text = current_subject
                raw_subject_text = current_subject
                subject_mention = None
                subject_source = "hu_hasznal_current_state_pattern"
    if language == "hu" and pred_f == "megszunt":
        megszunt_override = _extract_hu_megszunt_subject_object(text, predicate_idx)
        if megszunt_override is not None:
            subject_text, hu_object_override = megszunt_override
            raw_subject_text = subject_text
            subject_mention = None
            subject_source = "hu_megszunt_year_object_pattern"
    if not is_valid_subject_text(subject_text, language=language):
        subject_text = "" if suppress_inherited_subject else inherited_subject or ""
        subject_source = "inherited" if subject_text else subject_source if suppress_inherited_subject else "missing"
    if not is_valid_subject_text(subject_text, language=language):
        subject_text = ""
        subject_source = "missing"

    hu_hasznal_end = hu_hasznal_use_subject_end_char(
        language=language,
        pred_f=pred_f,
        predicate_idx=predicate_idx,
        subject_mention=subject_mention,
        subject_source=subject_source,
        use_head_end_idx=use_head_end_idx,
    )
    object_text = build_object_text(
        text,
        mentions=mentions,
        predicate=raw_predicate,
        predicate_end_idx=predicate_end_idx,
        predicate_idx=predicate_idx,
        language=language,
        next_predicate_idx=next_predicate_idx,
        subject_text=subject_text,
        subject_mention=subject_mention,
        hu_hasznal_subject_end=hu_hasznal_end,
    )
    if hu_object_override is not None:
        object_text = hu_object_override
    elif language == "hu" and pred_f == "felelt":
        felelt_override = _extract_hu_felelt_subject_object(text, predicate_idx)
        if felelt_override is not None:
            _, object_text = felelt_override
    display_predicate = (
        normalize_predicate_display(
            raw_predicate, text=text, language=language, pred_start=predicate_idx or 0, pred_end=predicate_end_idx or 0
        )
        if predicate_idx is not None and predicate_end_idx is not None
        else raw_predicate
    )
    if language == "hu":
        display_predicate, object_text = _split_hu_felelose_title_predicate(display_predicate, object_text)
    if language == "en":
        split = _split_en_role_at_org(display_predicate, object_text, subject_text)
        if split is not None:
            display_predicate, object_text = split
    claim_text = build_claim_text(text, subject_text, display_predicate, object_text)
    claim_type = guess_claim_type(display_predicate, object_text, claim_text, language=language)
    if claim_type == "state" and should_drop_state_object(
        object_text, subject_text, language=language, state_predicate_fold=pred_f
    ):
        object_text = None
        claim_text = build_claim_text(text, subject_text, display_predicate, object_text)
    if language == "en" and normalize_predicate(display_predicate) == "responsible" and object_text and fold_text(object_text) in {
        "previously",
        "earlier",
    }:
        refetch = re.search(
            r"\bresponsible\s+for\s+(.+?)(?:[.]+)?\s*$", text, flags=re.IGNORECASE | re.DOTALL
        )
        if refetch is not None:
            object_text = clean_object_slice(refetch.group(1).strip(), language=language) or None
        else:
            object_text = None
        claim_text = build_claim_text(text, subject_text, display_predicate, object_text)

    if display_predicate == "describes":
        confidence = 0.4
    elif subject_text and display_predicate and object_text:
        confidence = 0.78
    elif subject_text and display_predicate:
        confidence = 0.68
    else:
        confidence = 0.45

    pattern_name = infer_extraction_pattern_name(
        language=language,
        pred_f=pred_f,
        subject_source=subject_source,
        display_predicate=display_predicate,
        hu_hasznal_subject_end=hu_hasznal_end,
    )
    sanitizers_applied = subject_sanitizer_tags(raw_subject_text, subject_text, language=language)
    base_metadata = {
        "extractor": "ClaimExtractorV1",
        "claim_text": claim_text,
        "source_sentence_text": text,
        "predicate_found": display_predicate != "describes",
        "has_real_subject": bool(subject_text),
        "subject_source": subject_source,
    }
    if sanitizers_applied:
        base_metadata["sanitizers_applied"] = sanitizers_applied
    claim = Claim(
        tenant=sentence.tenant,
        corpus_uuid=sentence.corpus_uuid,
        source_id=sentence.source_id,
        document_id=sentence.document_id,
        sentence_id=sentence.id,
        subject_mention_id=(
            subject_mention.mention_id if subject_mention is not None and subject_text else find_best_mention_id(mentions, subject_text)
        ),
        object_mention_id=find_best_mention_id(mentions, object_text),
        subject_text=subject_text,
        predicate_text=display_predicate,
        object_text=object_text,
        claim_type=claim_type,
        confidence=confidence,
        metadata=attach_extraction_provenance(base_metadata, language=language, pattern_name=pattern_name),
    )
    return apply_claim_type_config(claim)
