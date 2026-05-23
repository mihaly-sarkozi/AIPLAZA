from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from apps.knowledge.domain.claim import Claim
from apps.knowledge.domain.semantic_block import SEMANTIC_BLOCK_BUILDER_VERSION, SemanticBlock
from apps.knowledge.domain.sentence import Sentence
from apps.knowledge.service.entity_key_normalization import canonicalize_entity_key
from apps.knowledge.service.language_rules import fold_text


def _text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _unique(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = _text(value)
        if not item or item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def _subject_key(value: str) -> str:
    return canonicalize_entity_key(value) or fold_text(value)


_WEAK_SUBJECT_PREFIXES = (
    "ne felejtsd",
    "ne felejtse",
    "ne feledje",
    "fontos hogy",
    "ahhoz hogy",
    "ha ",
    "amikor ",
    "amennyiben ",
    "kattints",
    "valaszd",
    "válaszd",
    "add meg",
    "meg kell",
)


def _is_weak_block_subject(value: str) -> bool:
    text = _text(value)
    folded = fold_text(text)
    if not folded:
        return True
    if any(folded.startswith(prefix) for prefix in _WEAK_SUBJECT_PREFIXES):
        return True
    if len(text.split()) > 6:
        return True
    return False


def _resolve_sentence_subject(claims: list[Claim], sentence: Sentence) -> tuple[str, str, float]:
    candidates = [_text(claim.subject_text) for claim in claims if not _is_weak_block_subject(_text(claim.subject_text))]
    if candidates:
        counts: dict[str, tuple[int, str]] = {}
        for candidate in candidates:
            key = _subject_key(candidate)
            count, _existing = counts.get(key, (0, candidate))
            counts[key] = (count + 1, candidate)
        return sorted(counts.values(), key=lambda item: (-item[0], len(item[1])))[0][1], "claim", 0.9
    header = _text(sentence.metadata.get("header_context_text"))
    if header and not _is_weak_block_subject(header):
        return header, "header", 0.6
    if claims:
        return _text(claims[0].subject_text), "weak_claim_fallback", 0.35
    words = _text(sentence.text_content).split()
    return " ".join(words[: min(4, len(words))]), "sentence_prefix_fallback", 0.25


def _predicate_key(value: str) -> str:
    folded = fold_text(value)
    for token in ("használ", "hasznal", "uses", "use", "funkció", "function", "feature", "beállítás", "setting"):
        if token in folded:
            return token
    return folded.split(" ", 1)[0] if folded else ""


def _context_values(claims: list[Claim], attr_name: str) -> list[str]:
    return _unique([str(getattr(claim, attr_name, "") or "") for claim in claims])


def _context_key(values: list[str], modes: list[str]) -> str:
    meaningful_values = [value for value in values if fold_text(value) not in {"", "unknown", "ismeretlen"}]
    if meaningful_values:
        return fold_text(meaningful_values[0])
    meaningful_modes = [mode for mode in modes if fold_text(mode) not in {"", "unknown", "ismeretlen"}]
    return fold_text(meaningful_modes[0]) if meaningful_modes else ""


@dataclass(frozen=True)
class _SentenceContext:
    sentence: Sentence
    claims: list[Claim]
    subject: str
    subject_key: str
    subject_source: str
    subject_confidence: float
    space_key: str
    space_value: str
    time_key: str
    time_value: str
    topic_key: str


def _resolve_sentence_context(sentence: Sentence, claims: list[Claim]) -> _SentenceContext:
    if claims:
        subject, subject_source, subject_confidence = _resolve_sentence_subject(claims, sentence)
        predicates = [_predicate_key(claim.predicate_text) for claim in claims if _predicate_key(claim.predicate_text)]
        space_values = _context_values(claims, "space_label")
        space_modes = _context_values(claims, "space_mode")
        time_values = _context_values(claims, "time_label")
        time_modes = _context_values(claims, "time_mode")
        return _SentenceContext(
            sentence=sentence,
            claims=claims,
            subject=subject,
            subject_key=_subject_key(subject),
            subject_source=subject_source,
            subject_confidence=subject_confidence,
            space_key=_context_key(space_values, space_modes),
            space_value=space_values[0] if space_values else "",
            time_key=_context_key(time_values, time_modes),
            time_value=time_values[0] if time_values else "",
            topic_key=predicates[0] if predicates else "",
        )
    header = _text(sentence.metadata.get("header_context_text"))
    if header:
        return _SentenceContext(
            sentence=sentence,
            claims=[],
            subject=header,
            subject_key=_subject_key(header),
            subject_source="header",
            subject_confidence=0.6,
            space_key="",
            space_value="",
            time_key="",
            time_value="",
            topic_key="header",
        )
    words = _text(sentence.text_content).split()
    subject = " ".join(words[: min(4, len(words))])
    return _SentenceContext(
        sentence=sentence,
        claims=[],
        subject=subject,
        subject_key=_subject_key(subject),
        subject_source="sentence_prefix_fallback",
        subject_confidence=0.25,
        space_key="",
        space_value="",
        time_key="",
        time_value="",
        topic_key="",
    )


def _is_boundary(
    *,
    current_subject_key: str,
    current_space_key: str,
    current_time_key: str,
    next_subject_key: str,
    next_space_key: str,
    next_time_key: str,
    sentence: Sentence,
    current_sentence_count: int,
) -> bool:
    block_type = str(sentence.metadata.get("block_type") or "")
    if block_type == "heading" and current_sentence_count > 0:
        return True
    if current_subject_key and next_subject_key and current_subject_key != next_subject_key:
        return True
    if current_space_key and next_space_key and current_space_key != next_space_key:
        return True
    if current_time_key and next_time_key and current_time_key != next_time_key:
        return True
    return False


@dataclass(frozen=True)
class _OpenBlock:
    first_context: _SentenceContext
    sentence_contexts: list[_SentenceContext]


class SemanticBlockBuilderV1:
    version = SEMANTIC_BLOCK_BUILDER_VERSION

    def build(self, *, sentences: list[Sentence], claims: list[Claim]) -> list[SemanticBlock]:
        claims_by_sentence: dict[str, list[Claim]] = {}
        for claim in claims:
            claims_by_sentence.setdefault(str(claim.sentence_id), []).append(claim)

        blocks: list[SemanticBlock] = []
        current: _OpenBlock | None = None
        for sentence in sorted(sentences, key=lambda item: item.order_index):
            sentence_claims = claims_by_sentence.get(sentence.id, [])
            sentence_context = _resolve_sentence_context(sentence, sentence_claims)
            if current is not None and _is_boundary(
                current_subject_key=current.first_context.subject_key,
                current_space_key=current.first_context.space_key,
                current_time_key=current.first_context.time_key,
                next_subject_key=sentence_context.subject_key,
                next_space_key=sentence_context.space_key,
                next_time_key=sentence_context.time_key,
                sentence=sentence,
                current_sentence_count=len(current.sentence_contexts),
            ):
                blocks.append(self._close(current))
                current = None
            if current is None:
                current = _OpenBlock(
                    first_context=sentence_context,
                    sentence_contexts=[sentence_context],
                )
                continue
            current.sentence_contexts.append(sentence_context)
        if current is not None:
            blocks.append(self._close(current))
        return blocks

    def _close(self, block: _OpenBlock) -> SemanticBlock:
        sentences = [context.sentence for context in block.sentence_contexts]
        claims = [claim for context in block.sentence_contexts for claim in context.claims]
        sentence_ids = [sentence.id for sentence in sentences]
        paragraph_ids = _unique([sentence.paragraph_id for sentence in sentences])
        claim_ids = _unique([claim.id for claim in claims])
        predicates = _unique([claim.predicate_text for claim in claims])
        entity_keys = _unique([context.subject_key for context in block.sentence_contexts] or [block.first_context.subject_key])
        space_modes = _unique([claim.space_mode for claim in claims])
        space_values = _unique([context.space_value for context in block.sentence_contexts])
        time_modes = _unique([claim.time_mode for claim in claims])
        time_values = _unique([context.time_value for context in block.sentence_contexts])
        confidence_values = [float(claim.confidence or 0.0) for claim in claims]
        confidence = sum(confidence_values) / len(confidence_values) if confidence_values else 0.5
        text = "\n".join(_text(sentence.text_content) for sentence in sentences if _text(sentence.text_content))
        order_values = [sentence.order_index for sentence in sentences]
        first_sentence = sentences[0] if sentences else Sentence()
        summary_parts = [block.first_context.subject]
        if predicates:
            summary_parts.append(", ".join(predicates[:3]))
        if space_values:
            summary_parts.append(f"hely: {space_values[0]}")
        if time_values:
            summary_parts.append(f"idő: {time_values[0]}")
        return SemanticBlock(
            corpus_uuid=first_sentence.corpus_uuid,
            source_id=first_sentence.source_id,
            document_id=first_sentence.document_id,
            paragraph_ids=paragraph_ids,
            sentence_ids=sentence_ids,
            claim_ids=claim_ids,
            order_start=min(order_values) if order_values else 0,
            order_end=max(order_values) if order_values else 0,
            primary_subject=block.first_context.subject,
            subject_key=block.first_context.subject_key,
            primary_space=block.first_context.space_value,
            space_key=block.first_context.space_key,
            primary_time=block.first_context.time_value,
            time_key=block.first_context.time_key,
            topic_key=block.first_context.topic_key,
            text=text,
            summary=" | ".join(part for part in summary_parts if part),
            predicates=predicates,
            entity_keys=entity_keys,
            space_modes=space_modes,
            space_values=space_values,
            time_modes=time_modes,
            time_values=time_values,
            confidence=confidence,
            metadata={
                "sentence_count": len(sentence_ids),
                "claim_count": len(claim_ids),
                "grouping_rule": "sentence_context_subject_space_time_v4",
                "sentence_contexts": [
                    {
                        "sentence_id": context.sentence.id,
                        "order_index": context.sentence.order_index,
                        "resolved_subject": context.subject,
                        "subject_key": context.subject_key,
                        "subject_source": context.subject_source,
                        "subject_confidence": context.subject_confidence,
                        "space_key": context.space_key,
                        "space_value": context.space_value,
                        "time_key": context.time_key,
                        "time_value": context.time_value,
                    }
                    for context in block.sentence_contexts
                ],
            },
        )


__all__ = ["SemanticBlockBuilderV1"]
