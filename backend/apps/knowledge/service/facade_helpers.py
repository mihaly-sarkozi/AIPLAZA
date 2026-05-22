# backend/apps/knowledge/service/facade_helpers.py
# Feladat: A KnowledgeFacade állapotmentes helper függvényeit és DTO-it tartalmazza. Text normalizálás, JSON-safe konverzió, ingest quality aggregálás és trace search profile visszaépítés logikáját választja le a túl nagy facade fájlról. Program-specifikus knowledge facade utility réteg.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
import unicodedata
import uuid as uuid_lib

from apps.knowledge.domain.ingest_item import IngestItem
from apps.knowledge.domain.search_profile import SearchProfile


@dataclass(frozen=True)
class SentenceCandidate:
    text: str
    confidence: float
    split_reason: str
    char_start_offset: int
    char_end_offset: int


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def is_uuid_string(value: str | None) -> bool:
    if not value:
        return False
    try:
        uuid_lib.UUID(str(value))
    except ValueError:
        return False
    return True


def normalize_text_payload(value: str | None) -> str:
    text = str(value or "")
    text = text.removeprefix("\ufeff")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return unicodedata.normalize("NFC", text)


def truncate_diagnostic_text(value: str | None, *, limit: int = 220) -> str:
    text = " ".join(str(value or "").strip().split())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)].rstrip() + "..."


def json_safe(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    if isinstance(value, tuple | set):
        return [json_safe(item) for item in value]
    return value


def empty_claim_quality_summary() -> dict[str, Any]:
    return {
        "skipped_sentence_count": 0,
        "rejected_claim_count": 0,
        "describes_claim_count": 0,
        "low_confidence_claim_count": 0,
        "bad_subject_claim_count": 0,
        "question_sentence_count": 0,
        "fragment_sentence_count": 0,
        "noise_sentence_skipped_count": 0,
        "noise_claim_rejected_count": 0,
        "weak_auxiliary_claim_rejected_count": 0,
        "duplicate_weak_claim_rejected_count": 0,
        "skipped_sentences": [],
        "rejected_claim_examples": [],
    }


def merge_claim_quality_summary(summary: dict[str, Any], diagnostics: dict[str, Any] | None) -> dict[str, Any]:
    if not diagnostics:
        return summary

    merged = {
        **empty_claim_quality_summary(),
        **dict(summary or {}),
    }
    if diagnostics.get("skipped"):
        merged["skipped_sentence_count"] = int(merged.get("skipped_sentence_count") or 0) + 1
        sentence_reason = str(diagnostics.get("sentence_reason") or "")
        if sentence_reason == "sentence_is_question":
            merged["question_sentence_count"] = int(merged.get("question_sentence_count") or 0) + 1
        elif sentence_reason in {"sentence_is_explicit_noise", "noise_sentence"}:
            merged["noise_sentence_skipped_count"] = int(merged.get("noise_sentence_skipped_count") or 0) + 1
        elif sentence_reason in {"sentence_is_fragment", "sentence_no_meaningful_content"}:
            merged["fragment_sentence_count"] = int(merged.get("fragment_sentence_count") or 0) + 1
        skipped_sentences = list(merged.get("skipped_sentences") or [])
        if len(skipped_sentences) < 10:
            skipped_sentences.append(
                {
                    "sentence_id": diagnostics.get("sentence_id"),
                    "reason": sentence_reason or None,
                    "language": diagnostics.get("language"),
                    "text": truncate_diagnostic_text(diagnostics.get("sentence_text")),
                }
            )
        merged["skipped_sentences"] = skipped_sentences

    rejected_claims = list(diagnostics.get("rejected_claims") or [])
    merged["rejected_claim_count"] = int(merged.get("rejected_claim_count") or 0) + len(rejected_claims)
    rejected_examples = list(merged.get("rejected_claim_examples") or [])
    for item in rejected_claims:
        reason = str(item.get("reason") or "")
        if reason == "claim_fallback_describes":
            merged["describes_claim_count"] = int(merged.get("describes_claim_count") or 0) + 1
        elif reason == "claim_low_confidence":
            merged["low_confidence_claim_count"] = int(merged.get("low_confidence_claim_count") or 0) + 1
        elif reason == "claim_bad_subject":
            merged["bad_subject_claim_count"] = int(merged.get("bad_subject_claim_count") or 0) + 1
        elif reason == "claim_weak_auxiliary":
            merged["weak_auxiliary_claim_rejected_count"] = int(merged.get("weak_auxiliary_claim_rejected_count") or 0) + 1
        elif reason == "claim_duplicate_weak":
            merged["duplicate_weak_claim_rejected_count"] = int(merged.get("duplicate_weak_claim_rejected_count") or 0) + 1
        elif reason in {"sentence_is_explicit_noise", "noise_sentence"}:
            merged["noise_claim_rejected_count"] = int(merged.get("noise_claim_rejected_count") or 0) + 1
        elif reason == "sentence_is_question" and not diagnostics.get("skipped"):
            merged["question_sentence_count"] = int(merged.get("question_sentence_count") or 0) + 1
        elif reason in {"sentence_is_fragment", "sentence_no_meaningful_content"} and not diagnostics.get("skipped"):
            merged["fragment_sentence_count"] = int(merged.get("fragment_sentence_count") or 0) + 1

        if len(rejected_examples) < 20:
            rejected_examples.append(
                {
                    "reason": reason or None,
                    "subject_text": truncate_diagnostic_text(item.get("subject_text"), limit=80),
                    "predicate": truncate_diagnostic_text(item.get("predicate"), limit=60),
                    "object_text": truncate_diagnostic_text(item.get("object_text"), limit=120),
                    "claim_type": item.get("claim_type"),
                    "confidence": item.get("confidence"),
                }
            )
    merged["rejected_claim_examples"] = rejected_examples
    return merged


def aggregate_ingest_item_quality(items: list[IngestItem]) -> dict[str, Any]:
    summary = empty_claim_quality_summary()
    has_quality = False
    for item in items:
        metadata = dict(getattr(item, "metadata", {}) or {})
        item_quality = metadata.get("interpretation_quality")
        if not isinstance(item_quality, dict):
            continue
        has_quality = True
        for key in (
            "skipped_sentence_count",
            "rejected_claim_count",
            "describes_claim_count",
            "low_confidence_claim_count",
            "bad_subject_claim_count",
            "question_sentence_count",
            "fragment_sentence_count",
            "noise_sentence_skipped_count",
            "noise_claim_rejected_count",
            "weak_auxiliary_claim_rejected_count",
            "duplicate_weak_claim_rejected_count",
        ):
            summary[key] = int(summary.get(key) or 0) + int(item_quality.get(key) or 0)
        skipped_sentences = list(summary.get("skipped_sentences") or [])
        for row in list(item_quality.get("skipped_sentences") or []):
            if len(skipped_sentences) >= 10:
                break
            skipped_sentences.append(row)
        summary["skipped_sentences"] = skipped_sentences

        rejected_examples = list(summary.get("rejected_claim_examples") or [])
        for row in list(item_quality.get("rejected_claim_examples") or []):
            if len(rejected_examples) >= 20:
                break
            rejected_examples.append(row)
        summary["rejected_claim_examples"] = rejected_examples
    if not has_quality:
        summary["todo"] = "TODO: persist rejected claim diagnostics per ingest run."
    return summary


def uuid_from_trace_value(value: Any) -> uuid_lib.UUID:
    text = str(value or "").strip()
    if text:
        try:
            return uuid_lib.UUID(text)
        except ValueError:
            return uuid_lib.uuid5(uuid_lib.NAMESPACE_URL, text)
    return uuid_lib.uuid4()


def optional_uuid_from_trace_value(value: Any) -> uuid_lib.UUID | None:
    text = str(value or "").strip()
    if not text:
        return None
    return uuid_from_trace_value(text)


def search_profile_from_trace_payload(payload: dict[str, Any]) -> SearchProfile | None:
    if not isinstance(payload, dict):
        return None
    entity_name = str(payload.get("entity_name") or "").strip()
    if not entity_name:
        return None
    return SearchProfile(
        search_profile_id=uuid_from_trace_value(payload.get("search_profile_id")),
        run_id=optional_uuid_from_trace_value(payload.get("run_id")),
        source_id=optional_uuid_from_trace_value(payload.get("source_id")),
        technical_memory_chunk_id=optional_uuid_from_trace_value(payload.get("technical_memory_chunk_id")),
        technical_entity_id=optional_uuid_from_trace_value(payload.get("technical_entity_id")),
        local_entity_id=optional_uuid_from_trace_value(payload.get("local_entity_id")),
        entity_name=entity_name,
        entity_type=str(payload.get("entity_type") or "unknown"),
        normalized_key=str(payload.get("normalized_key") or ""),
        canonical_key=str(payload.get("canonical_key") or payload.get("normalized_key") or ""),
        canonical_text=str(payload.get("canonical_text") or ""),
        search_text=str(payload.get("search_text") or ""),
        aliases=[str(item) for item in payload.get("aliases") or []],
        keywords=[str(item) for item in payload.get("keywords") or []],
        claim_group_signals=dict(payload.get("claim_group_signals") or {}),
        time_filters=dict(payload.get("time_filters") or {}),
        space_filters=dict(payload.get("space_filters") or {}),
        relation_filters=dict(payload.get("relation_filters") or {}),
        evidence_refs=[dict(item) for item in payload.get("evidence_refs") or [] if isinstance(item, dict)],
        builder_version=str(payload.get("builder_version") or "search_profile_builder_v1"),
    )


__all__ = [
    "SentenceCandidate",
    "aggregate_ingest_item_quality",
    "empty_claim_quality_summary",
    "is_uuid_string",
    "json_safe",
    "merge_claim_quality_summary",
    "normalize_text_payload",
    "optional_uuid_from_trace_value",
    "search_profile_from_trace_payload",
    "truncate_diagnostic_text",
    "utcnow",
    "uuid_from_trace_value",
]
