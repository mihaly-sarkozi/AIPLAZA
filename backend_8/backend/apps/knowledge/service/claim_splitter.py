"""Több-claim mondatok szegmentálása (subject carryover, max. 3 szegmens).

Nem futtat claim extrakciót: csak szövegdarabokat ad vissza, amelyek külön-külön
feldolgozhatók. A ``ClaimExtractorV1`` egy passban is kezel több predikátumot;
ez a modul kanonikus szegmentálást ad alternatív / előfeldolgozó útvonalakhoz.

Kezelt minták:
- EN: ``was created`` … ``and updated``
- ES: ``fue creada`` … ``y actualizada`` (és férfi: ``fue creado`` / ``y actualizado``)
- EN: állapot jelen + történeti: ``, but …`` (``it was`` → alany pótlás)
- ES: ``, pero …`` (azonos alany feltételezése, ha a jobb ág nem új NP-vel kezd)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, replace

from apps.knowledge.service.claim_extract_normalize import normalize_text
from apps.knowledge.service.claim_split.types import ClaimCandidate
from apps.knowledge.service.language_rules import fold_text

MAX_CLAIM_SEGMENTS = 3


def _dedupe_segments(segments: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for seg in segments:
        key = fold_text(normalize_text(seg))
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(normalize_text(seg))
    return out


def _en_subject_heading_state(clause: str) -> str | None:
    for pat in (
        r"^((?:the|a|an)\s+.+?)\s+is\s+",
        r"^((?:the|a|an)\s+.+?)\s+was\s+",
        r"^(.+?)\s+is\s+",
        r"^(.+?)\s+was\s+",
    ):
        m = re.match(pat, clause.strip(), flags=re.IGNORECASE | re.DOTALL)
        if m:
            return normalize_text(m.group(1))
    return None


def _es_subject_heading_state(clause: str) -> str | None:
    for pat in (
        r"^((?:el|la|los|las|un|una)\s+.+?)\s+(?:está|esta)\s+",
        r"^((?:el|la|los|las|un|una)\s+.+?)\s+estaba\s+",
        r"^(.+?)\s+(?:está|esta)\s+",
    ):
        m = re.match(pat, clause.strip(), flags=re.IGNORECASE | re.DOTALL)
        if m:
            return normalize_text(m.group(1))
    return None


def _en_split_created_updated(text: str) -> list[str] | None:
    m = re.match(
        r"^(?P<prefix>.+?)\bwas\s+created\b(?P<mid>[\s\S]*?)\band\s+updated\b(?P<tail>[\s\S]*)$",
        text.strip(),
        flags=re.IGNORECASE,
    )
    if not m:
        return None
    prefix = normalize_text(m.group("prefix"))
    mid = m.group("mid")
    tail = m.group("tail")
    seg1 = normalize_text(f"{prefix} was created{mid}")
    seg2 = normalize_text(f"{prefix} updated{tail}")
    if fold_text(seg1) == fold_text(seg2):
        return None
    return [seg1, seg2]


def _es_split_creada_actualizada(text: str) -> list[str] | None:
    patterns = (
        (
            r"^(?P<prefix>.+?)\bfue\s+creada\b(?P<mid>[\s\S]*?)\by\s+actualizada\b(?P<tail>[\s\S]*)$",
            "actualizada",
        ),
        (
            r"^(?P<prefix>.+?)\bfue\s+creado\b(?P<mid>[\s\S]*?)\by\s+actualizado\b(?P<tail>[\s\S]*)$",
            "actualizado",
        ),
    )
    for pat, second_pred in patterns:
        m = re.match(pat, text.strip(), flags=re.IGNORECASE)
        if not m:
            continue
        prefix = normalize_text(m.group("prefix"))
        mid = m.group("mid")
        tail = m.group("tail")
        if second_pred == "actualizada":
            seg1 = normalize_text(f"{prefix} fue creada{mid}")
        else:
            seg1 = normalize_text(f"{prefix} fue creado{mid}")
        seg2 = normalize_text(f"{prefix} {second_pred}{tail}")
        if fold_text(seg1) == fold_text(seg2):
            return None
        return [seg1, seg2]
    return None


def _en_split_state_but(text: str) -> list[str] | None:
    parts = re.split(r",\s*but\s+", text.strip(), maxsplit=1, flags=re.IGNORECASE)
    if len(parts) != 2:
        return None
    left, right = normalize_text(parts[0]), parts[1].strip()
    if not left or not right:
        return None
    if re.match(r"^it\s+was\b", right, flags=re.IGNORECASE):
        subj = _en_subject_heading_state(left)
        if subj:
            right = normalize_text(f"{subj} {right[3:].lstrip()}")
    seg1, seg2 = left, normalize_text(right)
    if fold_text(seg1) == fold_text(seg2):
        return None
    return [seg1, seg2]


def _es_split_state_pero(text: str) -> list[str] | None:
    parts = re.split(r",\s*pero\s+", text.strip(), maxsplit=1, flags=re.IGNORECASE)
    if len(parts) != 2:
        return None
    left, right = normalize_text(parts[0]), parts[1].strip()
    if not left or not right:
        return None
    if not re.match(r"^(?:el|la|los|las|un|una)\b", right, flags=re.IGNORECASE):
        subj = _es_subject_heading_state(left)
        if subj:
            right = normalize_text(f"{subj} {right}")
    seg1, seg2 = left, normalize_text(right)
    if fold_text(seg1) == fold_text(seg2):
        return None
    return [seg1, seg2]


@dataclass
class ClaimSplitter:
    """Szegmentálás nyelvenként; legfeljebb ``MAX_CLAIM_SEGMENTS`` darab."""

    max_segments: int = MAX_CLAIM_SEGMENTS

    def split_sentence(self, sentence_text: str, language: str) -> list[str]:
        text = normalize_text(sentence_text)
        if not text:
            return []
        lang = (language or "en").lower().split("-", maxsplit=1)[0]
        segments: list[str] | None = None
        if lang == "en":
            segments = _en_split_created_updated(text) or _en_split_state_but(text)
        elif lang == "es":
            segments = _es_split_creada_actualizada(text) or _es_split_state_pero(text)

        if not segments:
            return [text]
        segments = _dedupe_segments(segments)
        if len(segments) > self.max_segments:
            segments = segments[: self.max_segments]
        return segments if segments else [text]


def split_sentence(sentence_text: str, language: str, *, max_segments: int = MAX_CLAIM_SEGMENTS) -> list[str]:
    return ClaimSplitter(max_segments=max_segments).split_sentence(sentence_text, language)


def split_candidates(
    candidates: list[ClaimCandidate],
    sentence_text: str,
    language: str,
    *,
    max_segments: int = MAX_CLAIM_SEGMENTS,
) -> list[ClaimCandidate]:
    """NLP ``ClaimCandidate`` lista: ``text_span`` szerinti szegmentálás, duplikátum nélkül.

    A token/char mezők változatlanok maradnak (a finom token-pozíciókat a hívó frissítheti).
    """
    splitter = ClaimSplitter(max_segments=max_segments)
    base = normalize_text(sentence_text)
    out: list[ClaimCandidate] = []
    seen_fold: set[str] = set()
    for c in candidates:
        span_text = normalize_text(c.text_span) or base
        parts = splitter.split_sentence(span_text, language)
        if len(parts) == 1:
            key = fold_text(parts[0])
            if key not in seen_fold:
                seen_fold.add(key)
                out.append(c)
            continue
        for i, part in enumerate(parts):
            key = fold_text(part)
            if key in seen_fold:
                continue
            seen_fold.add(key)
            reasons = [*list(c.split_reason or []), f"claim_splitter_seg_{i}"]
            conf = float(c.confidence) * (0.92 if i else 1.0)
            out.append(
                replace(
                    c,
                    text_span=part,
                    split_reason=reasons,
                    confidence=min(1.0, conf),
                )
            )
    return out


__all__ = [
    "MAX_CLAIM_SEGMENTS",
    "ClaimSplitter",
    "split_candidates",
    "split_sentence",
]
