from __future__ import annotations

import calendar
from datetime import UTC, datetime
from typing import Any

from apps.knowledge.application.assertion_fingerprinter import (
    build_assertion_fingerprint as _build_assertion_fingerprint,
)
from apps.knowledge.application.sentence_splitter import split_sentences as _split_sentences
from apps.knowledge.application.structural_chunker import (
    build_structural_chunks as _build_structural_chunks,
)
from apps.knowledge.application.scoring import (
    compute_confidence,
    compute_relation_confidence,
    determine_assertion_status,
)
from apps.knowledge.ports.assertion_extractor_port import AssertionExtractorPort
from apps.knowledge.ports.repositories import KnowledgeBaseRepositoryPort
from apps.knowledge.ports.vector_index_port import VectorIndexPort

def _normalize_key(value: str) -> str:
    return (value or "").strip().lower()


def _utcnow_naive() -> datetime:
    """UTC now timezone-naive formában."""
    return datetime.now(UTC).replace(tzinfo=None)


def build_assertion_fingerprint(
    kb_id: int,
    subject_key: str,
    predicate: str,
    object_key: str,
    time_bucket: str,
    place_key: str,
) -> str:
    """Visszafelé kompatibilis fingerprint wrapper."""
    return _build_assertion_fingerprint(
        kb_id=kb_id,
        subject_key=subject_key,
        predicate=predicate,
        object_key=object_key,
        time_bucket=time_bucket,
        place_key=place_key,
    )


def _same_core_fact(a1: dict[str, Any], a2: dict[str, Any]) -> bool:
    return (
        int(a1.get("subject_entity_id") or 0) > 0
        and int(a1.get("subject_entity_id") or 0) == int(a2.get("subject_entity_id") or 0)
        and str(a1.get("predicate") or "").strip().lower() == str(a2.get("predicate") or "").strip().lower()
        and (
            (int(a1.get("object_entity_id") or 0) > 0 and int(a1.get("object_entity_id") or 0) == int(a2.get("object_entity_id") or 0))
            or (
                not a1.get("object_entity_id")
                and not a2.get("object_entity_id")
                and str(a1.get("object_value") or "").strip().lower() == str(a2.get("object_value") or "").strip().lower()
            )
        )
    )


def _is_narrower_time(a_new: dict[str, Any], a_old: dict[str, Any]) -> bool:
    new_from, new_to = a_new.get("time_from"), a_new.get("time_to")
    old_from, old_to = a_old.get("time_from"), a_old.get("time_to")
    if not new_from and not new_to:
        return False
    if not old_from and not old_to:
        return False
    if new_from and old_from and new_from < old_from:
        return False
    if new_to and old_to and new_to > old_to:
        return False
    if new_from == old_from and new_to == old_to:
        return False
    return True


def _is_contradiction_candidate(a1: dict[str, Any], a2: dict[str, Any]) -> bool:
    if not _same_core_fact(a1, a2):
        return False
    a1_from, a1_to = a1.get("time_from"), a1.get("time_to")
    a2_from, a2_to = a2.get("time_from"), a2.get("time_to")
    if a1_from is None and a1_to is None:
        return False
    if a2_from is None and a2_to is None:
        return False
    af = a1_from or a1_to
    at = a1_to or a1_from
    bf = a2_from or a2_to
    bt = a2_to or a2_from
    if af is None or at is None or bf is None or bt is None:
        return False
    if (at < bf) or (bt < af):
        return False
    pol1 = str(a1.get("polarity") or "positive").strip().lower()
    pol2 = str(a2.get("polarity") or "positive").strip().lower()
    if pol1 != pol2:
        return True
    val1 = str(a1.get("object_value") or "").strip().lower()
    val2 = str(a2.get("object_value") or "").strip().lower()
    return bool(val1 and val2 and val1 != val2)


class KnowledgeIndexingPipeline:
    """Sanitized content indexing pipeline (sentence/chunk/assertion/entity)."""

    def __init__(
        self,
        repo: KnowledgeBaseRepositoryPort,
        vector_index: VectorIndexPort,
        extractor: AssertionExtractorPort | None = None,
    ) -> None:
        self.repo = repo
        self.vector_index = vector_index
        self.extractor = extractor

    def split_sentences(self, text: str) -> list[str]:
        """Mondathatárok mentén vágás, sorrend megtartásával."""
        return _split_sentences(text)

    def build_structural_chunks(
        self,
        sentences: list[dict[str, Any]],
        min_tokens: int = 350,
        target_tokens: int = 520,
        max_tokens: int = 700,
        overlap_ratio: float = 0.12,
    ) -> list[dict[str, Any]]:
        """350-700 token körüli chunkok mondathatáron, mérsékelt overlap-pel."""
        return _build_structural_chunks(
            sentences=sentences,
            min_tokens=min_tokens,
            target_tokens=target_tokens,
            max_tokens=max_tokens,
            overlap_ratio=overlap_ratio,
        )

    async def index_training_content(
        self,
        kb_id: int,
        kb_uuid: str,
        collection: str,
        source_point_id: str,
        sanitized_text: str,
        title: str,
        current_user_id: int | None = None,
    ) -> dict[str, Any]:
        """Training log után indexelés: sentence/chunk + opcionális assertions."""
        _ = current_user_id  # későbbi scoring/reinforcement bővítéshez.
        await self.vector_index.ensure_collection_schema(collection)
        ingest_time = _utcnow_naive()

        def _parse_time_value(raw: Any) -> tuple[datetime | None, str]:
            text = str(raw or "").strip()
            if not text:
                return None, "unknown"
            try:
                return datetime.fromisoformat(text.replace("Z", "+00:00")).replace(tzinfo=None), "day"
            except Exception:
                pass
            if len(text) == 4 and text.isdigit():
                year = int(text)
                return datetime(year, 1, 1), "year"
            if len(text) == 7 and text[4] == "-":
                try:
                    year = int(text[:4])
                    month = int(text[5:7])
                    return datetime(year, month, 1), "month"
                except Exception:
                    return None, "unknown"
            return None, "unknown"

        def _parse_time_interval(time_from_raw: Any, time_to_raw: Any) -> tuple[datetime | None, datetime | None, str]:
            start, gran_from = _parse_time_value(time_from_raw)
            end, gran_to = _parse_time_value(time_to_raw)
            granularity = gran_from if gran_from != "unknown" else gran_to
            if start and not end:
                if granularity == "year":
                    end = datetime(start.year, 12, 31, 23, 59, 59)
                elif granularity == "month":
                    last = calendar.monthrange(start.year, start.month)[1]
                    end = datetime(start.year, start.month, last, 23, 59, 59)
                else:
                    end = datetime(start.year, start.month, start.day, 23, 59, 59)
            if end and not start:
                if granularity == "year":
                    start = datetime(end.year, 1, 1)
                elif granularity == "month":
                    start = datetime(end.year, end.month, 1)
                else:
                    start = datetime(end.year, end.month, end.day)
            return start, end, granularity or "unknown"

        def _parse_candidate_time(candidate: dict[str, Any]) -> tuple[datetime | None, datetime | None, str]:
            time_from_raw = (
                candidate.get("time_from")
                or candidate.get("valid_from")
                or candidate.get("start")
                or candidate.get("from")
                or candidate.get("value")
            )
            time_to_raw = (
                candidate.get("time_to")
                or candidate.get("valid_to")
                or candidate.get("end")
                or candidate.get("to")
                or candidate.get("value")
            )
            return _parse_time_interval(time_from_raw=time_from_raw, time_to_raw=time_to_raw)

        def _time_bucket(start: datetime | None, end: datetime | None, granularity: str) -> str:
            if start is None and end is None:
                return ""
            ref = start or end
            if ref is None:
                return ""
            if granularity == "year":
                return f"{ref.year}"
            if granularity == "month":
                return f"{ref.year:04d}-{ref.month:02d}"
            return ref.strftime("%Y-%m-%d")

        def _canonical_text_with_meta(
            base_text: str,
            valid_time_from: datetime | None,
            valid_time_to: datetime | None,
            place_key: str | None,
        ) -> str:
            base = (base_text or "").strip()
            extras: list[str] = []
            if valid_time_from or valid_time_to:
                from_s = valid_time_from.date().isoformat() if valid_time_from else "?"
                to_s = valid_time_to.date().isoformat() if valid_time_to else "?"
                extras.append(f"valid_time={from_s}..{to_s}")
            if place_key:
                extras.append(f"place={place_key}")
            if not extras:
                return base
            return f"{base} | " + " | ".join(extras)

        sentence_texts = self.split_sentences(sanitized_text)
        sentence_rows = self.repo.create_sentence_batch(
            kb_id=kb_id,
            source_point_id=source_point_id,
            rows=[
                {
                    "sentence_order": i,
                    "text": s,
                    "sanitized_text": s,
                    "token_count": len(s.split()),
                }
                for i, s in enumerate(sentence_texts)
            ],
        )
        sentence_by_index = {int(row["sentence_order"]): row for row in sentence_rows}

        chunk_seed = [
            {
                "id": row["id"],
                "sanitized_text": row["sanitized_text"],
                "token_count": row["token_count"],
            }
            for row in sentence_rows
        ]
        chunk_rows = self.repo.create_structural_chunk_batch(
            kb_id=kb_id,
            source_point_id=source_point_id,
            rows=self.build_structural_chunks(chunk_seed),
        )

        assertion_count = 0
        entity_count = 0
        extraction_failed = False
        evidence_count = 0
        mention_count = 0
        relation_count = 0
        sentence_meta: dict[int, dict[str, Any]] = {
            int(row["id"]): {
                "id": int(row["id"]),
                "entity_ids": [],
                "assertion_ids": [],
                "predicate_hints": [],
                "valid_time_from": None,
                "valid_time_to": None,
                "place_ids": [],
                "place_keys": [],
            }
            for row in sentence_rows
        }

        def _merge_valid_time(meta: dict[str, Any], start: datetime | None, end: datetime | None) -> None:
            if start is not None:
                current_start = meta.get("valid_time_from")
                meta["valid_time_from"] = start if current_start is None else min(current_start, start)
            if end is not None:
                current_end = meta.get("valid_time_to")
                meta["valid_time_to"] = end if current_end is None else max(current_end, end)

        def _intervals_overlap(a_from: datetime | None, a_to: datetime | None, b_from: datetime | None, b_to: datetime | None) -> bool:
            if a_from is None and a_to is None:
                return False
            if b_from is None and b_to is None:
                return False
            af = a_from or a_to
            at = a_to or a_from
            bf = b_from or b_to
            bt = b_to or b_from
            if af is None or at is None or bf is None or bt is None:
                return False
            return not (at < bf or bt < af)

        sentence_mentions: dict[int, list[dict[str, Any]]] = {int(x["id"]): [] for x in sentence_rows}
        sentence_index_to_id: dict[int, int] = {
            int(row["sentence_order"]): int(row["id"])
            for row in sentence_rows
        }

        assertion_by_id: dict[int, dict[str, Any]] = {}
        if self.extractor is not None and sanitized_text.strip():
            try:
                extracted = await self.extractor.extract(sanitized_text=sanitized_text, title=title)
                extraction_conf = float(extracted.get("extraction_confidence") or 0.0)
                default_source_time = _parse_time_value(extracted.get("source_time"))[0]
                by_name: dict[str, dict] = {}
                entity_points: list[dict[str, Any]] = []
                for e in extracted.get("entities", []):
                    entity = self.repo.upsert_entity(
                        kb_id=kb_id,
                        payload={
                            "source_point_id": source_point_id,
                            "canonical_name": e.get("canonical_name"),
                            "entity_type": e.get("entity_type", "UNKNOWN"),
                            "aliases": e.get("aliases", []),
                            "confidence": float(e.get("confidence") or 0.0),
                        },
                    )
                    by_name[_normalize_key(entity["canonical_name"])] = entity
                    entity_points.append(
                        {
                            "id": f"entity-{entity['id']}",
                            "text": " | ".join(
                                [
                                    str(entity.get("canonical_name") or ""),
                                    ", ".join(entity.get("aliases") or []),
                                    str(entity.get("entity_type") or ""),
                                ]
                            ).strip(" |"),
                            "payload": {
                                "entity_id": int(entity["id"]),
                                "kb_id": kb_id,
                                "kb_uuid": kb_uuid,
                                "source_point_id": source_point_id,
                                "canonical_name": entity.get("canonical_name"),
                                "canonical_key": entity.get("canonical_key"),
                                "aliases": entity.get("aliases") or [],
                                "entity_type": entity.get("entity_type"),
                                "confidence": float(entity.get("confidence") or 0.0),
                            },
                        }
                    )
                    entity_count += 1

                if entity_points:
                    await self.vector_index.upsert_entity_points(collection=collection, rows=entity_points)

                place_candidates_by_sentence: dict[int, list[dict[str, Any]]] = {}
                place_candidates_by_key: dict[str, dict[str, Any]] = {}
                place_records_by_key: dict[str, dict[str, Any]] = {}

                def _upsert_place_record(place_key: str, place_candidate: dict[str, Any], canonical_name: str | None = None) -> dict[str, Any] | None:
                    if not place_key:
                        return None
                    existing = place_records_by_key.get(place_key)
                    if existing is not None:
                        return existing
                    parent_place_id = None
                    parent_name_raw = str(
                        place_candidate.get("parent_place")
                        or place_candidate.get("parent_name")
                        or place_candidate.get("parent_key")
                        or ""
                    ).strip()
                    if parent_name_raw:
                        parent_key = _normalize_key(parent_name_raw)
                        if parent_key and parent_key != place_key:
                            parent_record = _upsert_place_record(
                                place_key=parent_key,
                                place_candidate={
                                    "canonical_name": parent_name_raw,
                                    "place_type": place_candidate.get("parent_place_type"),
                                    "country_code": place_candidate.get("country_code"),
                                    "confidence": float(place_candidate.get("confidence") or extraction_conf or 0.0),
                                },
                                canonical_name=parent_name_raw,
                            )
                            if parent_record is not None:
                                parent_place_id = int(parent_record["id"])
                    record = self.repo.upsert_place(
                        kb_id=kb_id,
                        payload={
                            "canonical_name": str(
                                canonical_name
                                or place_candidate.get("canonical_name")
                                or place_candidate.get("place_key")
                                or place_candidate.get("text")
                                or place_key
                            ).strip() or place_key,
                            "normalized_key": place_key,
                            "place_type": place_candidate.get("place_type"),
                            "country_code": place_candidate.get("country_code"),
                            "parent_place_id": parent_place_id,
                            "confidence": float(place_candidate.get("confidence") or extraction_conf or 0.0),
                        },
                    )
                    place_records_by_key[place_key] = record
                    return record

                def _place_hierarchy_keys_for_records(place_ids: list[int], place_keys: list[str]) -> list[str]:
                    by_id = {
                        int(v["id"]): v
                        for v in place_records_by_key.values()
                        if v.get("id") is not None
                    }
                    ordered: list[str] = []
                    seen: set[str] = set()
                    for place_id in place_ids:
                        current_id = int(place_id)
                        visited: set[int] = set()
                        while current_id > 0 and current_id not in visited:
                            visited.add(current_id)
                            row = by_id.get(current_id)
                            if row is None:
                                break
                            key = str(row.get("normalized_key") or "").strip()
                            if key and key not in seen:
                                seen.add(key)
                                ordered.append(key)
                            parent_id = row.get("parent_place_id")
                            current_id = int(parent_id) if parent_id is not None else 0
                    for place_key in place_keys:
                        normalized = _normalize_key(place_key)
                        if normalized and normalized not in seen:
                            seen.add(normalized)
                            ordered.append(normalized)
                    return ordered
                for candidate in extracted.get("place_candidates", []) or []:
                    sent_idx = candidate.get("source_sentence_index")
                    if isinstance(sent_idx, int):
                        place_candidates_by_sentence.setdefault(int(sent_idx), []).append(candidate)
                    candidate_key = _normalize_key(
                        str(
                            candidate.get("normalized_key")
                            or candidate.get("canonical_name")
                            or candidate.get("place_key")
                            or candidate.get("text")
                            or candidate.get("value")
                            or ""
                        )
                    )
                    if candidate_key:
                        place_candidates_by_key[candidate_key] = candidate

                # Place dimenzió explicit persist már a jelöltekből is (akkor is, ha nincs assertion).
                for place_key, place_candidate in place_candidates_by_key.items():
                    _upsert_place_record(place_key=place_key, place_candidate=place_candidate)

                # Sentence place enrichment place_candidates alapján assertion nélkül is.
                for sent_idx, candidates in place_candidates_by_sentence.items():
                    source_sentence = sentence_by_index.get(int(sent_idx))
                    if source_sentence is None:
                        continue
                    meta = sentence_meta.get(int(source_sentence["id"]))
                    if meta is None:
                        continue
                    for candidate in candidates:
                        p_key = _normalize_key(
                            str(
                                candidate.get("normalized_key")
                                or candidate.get("canonical_name")
                                or candidate.get("place_key")
                                or candidate.get("text")
                                or candidate.get("value")
                                or ""
                            )
                        )
                        if p_key:
                            meta["place_keys"].append(p_key)
                            place_record = _upsert_place_record(place_key=p_key, place_candidate=candidate)
                            if place_record is not None:
                                meta["place_ids"].append(int(place_record["id"]))
                time_candidates_by_sentence: dict[int, list[dict[str, Any]]] = {}
                for candidate in extracted.get("time_candidates", []) or []:
                    sent_idx = candidate.get("source_sentence_index")
                    if not isinstance(sent_idx, int):
                        continue
                    time_candidates_by_sentence.setdefault(int(sent_idx), []).append(candidate)

                for mention in extracted.get("mentions", []):
                    sent_idx = mention.get("source_sentence_index")
                    if not isinstance(sent_idx, int):
                        continue
                    source_sentence = sentence_by_index.get(int(sent_idx))
                    if source_sentence is None:
                        continue
                    resolved = by_name.get(
                        _normalize_key(
                            mention.get("resolved_entity_candidate_name")
                            or mention.get("resolved_entity")
                            or mention.get("surface_form")
                            or ""
                        )
                    )
                    persisted = self.repo.create_mentions_batch(
                        sentence_id=int(source_sentence["id"]),
                        rows=[
                            {
                                "surface_form": mention.get("surface_form") or "",
                                "mention_type": mention.get("mention_type") or "UNKNOWN",
                                "grammatical_role": mention.get("grammatical_role"),
                                "sentence_local_index": mention.get("sentence_local_index"),
                                "char_start": mention.get("char_start"),
                                "char_end": mention.get("char_end"),
                                "resolved_entity_id": (resolved or {}).get("id"),
                                "resolution_confidence": float(mention.get("resolution_confidence") or 0.0),
                                "is_implicit_subject": bool(mention.get("is_implicit_subject")),
                            }
                        ],
                    )
                    mention_count += len(persisted)
                    sentence_mentions[int(source_sentence["id"])].extend(persisted)
                    meta = sentence_meta.get(int(source_sentence["id"]))
                    if meta is not None:
                        mention_ids = meta.setdefault("mention_ids", [])
                        for row in persisted:
                            if int(row.get("id") or 0) > 0:
                                mention_ids.append(int(row["id"]))

                assertion_points: list[dict[str, Any]] = []
                for a in extracted.get("assertions", []):
                    subject_key = _normalize_key(a.get("subject") or "")
                    object_value = a.get("object_value", a.get("object"))
                    object_key = _normalize_key(a.get("object_entity") or object_value or "")
                    subject_entity = by_name.get(subject_key)
                    object_entity = by_name.get(_normalize_key(a.get("object_entity") or ""))
                    source_sentence_id = None
                    source_sentence_idx = a.get("source_sentence_index")
                    if isinstance(source_sentence_idx, int):
                        source_sentence = sentence_by_index.get(source_sentence_idx)
                        if source_sentence is not None:
                            source_sentence_id = int(source_sentence["id"])

                    subject_resolution_type = "explicit"
                    if bool(a.get("subject_is_implicit")) or subject_key == _normalize_key("<implicit_subject>"):
                        subject_resolution_type = "implicit"
                    elif (subject_entity or {}).get("id") is None:
                        subject_resolution_type = "inferred"

                    primary_subject_mention_id = None
                    if source_sentence_id is not None:
                        sentence_mention_rows = sentence_mentions.get(int(source_sentence_id), [])
                        for m in sentence_mention_rows:
                            if bool(m.get("is_implicit_subject")) and subject_resolution_type == "implicit":
                                primary_subject_mention_id = int(m["id"])
                                break
                            if _normalize_key(m.get("surface_form") or "") == subject_key:
                                primary_subject_mention_id = int(m["id"])
                                break
                        if primary_subject_mention_id is None and subject_resolution_type == "implicit":
                            created = self.repo.create_mentions_batch(
                                sentence_id=int(source_sentence_id),
                                rows=[
                                    {
                                        "surface_form": "<implicit_subject>",
                                        "mention_type": "implicit_subject",
                                        "grammatical_role": "subject",
                                        "resolved_entity_id": (subject_entity or {}).get("id"),
                                        "resolution_confidence": float(a.get("confidence") or extraction_conf or 0.0),
                                        "is_implicit_subject": True,
                                    }
                                ],
                            )
                            mention_count += len(created)
                            sentence_mentions[int(source_sentence_id)].extend(created)
                            if created:
                                primary_subject_mention_id = int(created[0]["id"])

                    valid_time_from, valid_time_to, granularity = _parse_time_interval(
                        a.get("time_from"),
                        a.get("time_to"),
                    )
                    if valid_time_from is None and valid_time_to is None and isinstance(source_sentence_idx, int):
                        for tc in time_candidates_by_sentence.get(int(source_sentence_idx), []):
                            c_from, c_to, c_granularity = _parse_candidate_time(tc)
                            if c_from is not None or c_to is not None:
                                valid_time_from, valid_time_to, granularity = c_from, c_to, c_granularity
                                break
                    time_interval_id = None
                    if valid_time_from is not None or valid_time_to is not None:
                        time_record = self.repo.upsert_time_interval(
                            kb_id=kb_id,
                            payload={
                                "source_point_id": source_point_id,
                                "normalized_text": str(a.get("time_from") or a.get("time_to") or ""),
                                "valid_from": valid_time_from,
                                "valid_to": valid_time_to,
                                "granularity": granularity,
                                "confidence": float(a.get("confidence") or extraction_conf or 0.0),
                            },
                        )
                        time_interval_id = int(time_record["id"])

                    place_key_raw = (a.get("place_key") or a.get("place") or "").strip()
                    if not place_key_raw and isinstance(source_sentence_idx, int):
                        for pc in place_candidates_by_sentence.get(int(source_sentence_idx), []):
                            place_key_raw = str(
                                pc.get("normalized_key")
                                or pc.get("canonical_name")
                                or pc.get("place_key")
                                or pc.get("text")
                                or pc.get("value")
                                or ""
                            ).strip()
                            if place_key_raw:
                                break
                    place_key = _normalize_key(place_key_raw)
                    place_id = None
                    if place_key:
                        place_candidate = place_candidates_by_key.get(place_key) or {}
                        place_record = _upsert_place_record(
                            place_key=place_key,
                            place_candidate={
                                **place_candidate,
                                "confidence": float(a.get("confidence") or extraction_conf or 0.0),
                            },
                            canonical_name=place_key_raw or place_key,
                        )
                        if place_record is not None:
                            place_id = int(place_record["id"])

                    canonical_text = _canonical_text_with_meta(
                        base_text=a.get("canonical_text") or "",
                        valid_time_from=valid_time_from,
                        valid_time_to=valid_time_to,
                        place_key=place_key or None,
                    )
                    fingerprint = _build_assertion_fingerprint(
                        kb_id=kb_id,
                        subject_key=subject_key,
                        predicate=a.get("predicate") or "",
                        object_key=object_key,
                        time_bucket=_time_bucket(valid_time_from, valid_time_to, granularity),
                        place_key=place_key,
                        modality=str(a.get("modality") or "asserted"),
                        polarity=str(a.get("polarity") or "positive"),
                    )
                    confidence = compute_confidence(
                        extraction_confidence=float(a.get("confidence") or extraction_conf or 0.0),
                        source_quality=0.85,
                        evidence_count=1,
                        source_diversity=1,
                    )
                    assertion = self.repo.upsert_assertion(
                        kb_id=kb_id,
                        payload={
                            "source_point_id": source_point_id,
                            "source_document_title": title,
                            "source_sentence_id": source_sentence_id,
                            "assertion_primary_subject_mention_id": primary_subject_mention_id,
                            "subject_resolution_type": subject_resolution_type,
                            "subject_entity_id": (subject_entity or {}).get("id"),
                            "predicate": a.get("predicate") or "",
                            "object_entity_id": (object_entity or {}).get("id"),
                            "object_value": object_value,
                            "time_interval_id": time_interval_id,
                            "place_id": place_id,
                            "valid_time_from": valid_time_from,
                            "valid_time_to": valid_time_to,
                            "time_from": valid_time_from,
                            "time_to": valid_time_to,
                            "place_key": place_key,
                            "attributes": a.get("attributes", []),
                            "canonical_text": canonical_text,
                            "modality": str(a.get("modality") or "asserted"),
                            "polarity": str(a.get("polarity") or "positive"),
                            "source_time": _parse_time_value(a.get("source_time"))[0] or default_source_time,
                            "ingest_time": ingest_time,
                            "confidence": confidence,
                            "strength": 0.05,
                            "baseline_strength": 0.05,
                            "decay_rate": 0.015,
                            "status": determine_assertion_status(confidence=confidence, evidence_count=1),
                            "assertion_fingerprint": fingerprint,
                            "evidence_count": 1,
                        },
                    )
                    assertion_id = int(assertion["id"])
                    assertion_by_id[assertion_id] = assertion
                    if source_sentence_id is not None:
                        self.repo.add_assertion_evidence(
                            kb_id=kb_id,
                            assertion_id=assertion_id,
                            sentence_id=source_sentence_id,
                            source_point_id=source_point_id,
                            evidence_type="PRIMARY",
                            confidence=float(a.get("confidence") or extraction_conf or 0.0),
                            weight=1.0,
                        )
                        evidence_count += 1
                        meta = sentence_meta.get(int(source_sentence_id))
                        if meta is not None:
                            if (subject_entity or {}).get("id") is not None:
                                meta["entity_ids"].append(int(subject_entity["id"]))
                            if (object_entity or {}).get("id") is not None:
                                meta["entity_ids"].append(int(object_entity["id"]))
                            meta["assertion_ids"].append(assertion_id)
                            predicate_hint = str(assertion.get("predicate") or "").strip()
                            if predicate_hint:
                                meta["predicate_hints"].append(predicate_hint)
                            _merge_valid_time(meta, valid_time_from, valid_time_to)
                            if place_key:
                                meta["place_keys"].append(place_key)
                            if place_id is not None:
                                meta["place_ids"].append(int(place_id))
                            evidence_assertion_ids = meta.setdefault("evidence_assertion_ids", [])
                            evidence_assertion_ids.append(assertion_id)

                    self.repo.add_reinforcement_event(
                        kb_id=kb_id,
                        target_type="assertion",
                        target_id=assertion_id,
                        event_type="EXPLICIT_TRAINING" if bool(assertion.get("created")) else "SOURCE_CONFIRMATION",
                        weight=1.0,
                    )
                    assertion_points.append(
                        {
                            "id": f"assertion-{assertion_id}",
                            "text": assertion["canonical_text"],
                            "payload": {
                                "assertion_id": assertion_id,
                                "kb_uuid": kb_uuid,
                                "kb_id": kb_id,
                                "source_point_id": source_point_id,
                                "source_sentence_id": assertion.get("source_sentence_id"),
                                "assertion_primary_subject_mention_id": assertion.get("assertion_primary_subject_mention_id"),
                                "subject_resolution_type": assertion.get("subject_resolution_type"),
                                "subject_entity_id": assertion.get("subject_entity_id"),
                                "object_entity_id": assertion.get("object_entity_id"),
                                "assertion_fingerprint": assertion.get("assertion_fingerprint"),
                                "entity_ids": [x for x in [assertion.get("subject_entity_id"), assertion.get("object_entity_id")] if x],
                                "predicate": assertion.get("predicate"),
                                "place_id": assertion.get("place_id"),
                                "time_from": assertion.get("valid_time_from").isoformat() if assertion.get("valid_time_from") else None,
                                "time_to": assertion.get("valid_time_to").isoformat() if assertion.get("valid_time_to") else None,
                                "valid_time_from": assertion.get("valid_time_from").isoformat() if assertion.get("valid_time_from") else None,
                                "valid_time_to": assertion.get("valid_time_to").isoformat() if assertion.get("valid_time_to") else None,
                                "place_keys": [assertion.get("place_key")] if assertion.get("place_key") else [],
                                "place_hierarchy_keys": _place_hierarchy_keys_for_records(
                                    place_ids=[int(assertion.get("place_id"))] if assertion.get("place_id") is not None else [],
                                    place_keys=[assertion.get("place_key")] if assertion.get("place_key") else [],
                                ),
                                "source_time": assertion.get("source_time").isoformat() if assertion.get("source_time") else None,
                                "ingest_time": assertion.get("ingest_time").isoformat() if assertion.get("ingest_time") else None,
                                "confidence": assertion.get("confidence"),
                                "strength": assertion.get("strength"),
                                "baseline_strength": assertion.get("baseline_strength"),
                                "decay_rate": assertion.get("decay_rate"),
                                "last_reinforced_at": assertion.get("last_reinforced_at").isoformat() if assertion.get("last_reinforced_at") else None,
                                "status": assertion.get("status"),
                                "reinforcement_count": assertion.get("reinforcement_count"),
                                "source_document_title": title,
                            },
                        }
                    )
                    assertion_count += 1

                if assertion_points:
                    await self.vector_index.upsert_assertion_points(collection=collection, rows=assertion_points)

                # Lokális assertion gráf kapcsolatok build (source_point scope + P3 reasoning).
                relation_rows: list[dict[str, Any]] = []
                assertion_items = list(assertion_by_id.values())
                for i in range(len(assertion_items)):
                    a1 = assertion_items[i]
                    for j in range(i + 1, len(assertion_items)):
                        a2 = assertion_items[j]
                        rels: list[tuple[str, float]] = []
                        if a1.get("subject_entity_id") and a1.get("subject_entity_id") == a2.get("subject_entity_id"):
                            rels.append(("SAME_SUBJECT", 0.9))
                        if a1.get("object_entity_id") and a1.get("object_entity_id") == a2.get("object_entity_id"):
                            rels.append(("SAME_OBJECT", 0.8))
                        if (a1.get("predicate") or "").strip() and a1.get("predicate") == a2.get("predicate"):
                            rels.append(("SAME_PREDICATE", 0.65))
                        if (a1.get("place_key") or "").strip() and a1.get("place_key") == a2.get("place_key"):
                            rels.append(("SAME_PLACE", 0.5))
                        if (a1.get("source_point_id") or "").strip() and a1.get("source_point_id") == a2.get("source_point_id"):
                            rels.append(("SAME_SOURCE_POINT", 0.45))
                        if _intervals_overlap(a1.get("valid_time_from"), a1.get("valid_time_to"), a2.get("valid_time_from"), a2.get("valid_time_to")):
                            rels.append(("TEMPORALLY_OVERLAPS", 0.7))
                        if _same_core_fact(a1, a2):
                            rels.append(("SUPPORTS", 0.72))
                            if _is_narrower_time(a1, a2):
                                rels.append(("REFINES", 0.82))
                                rels.append(("GENERALIZES", 0.50))
                                rels.append(("TEMPORALLY_SPLITS", 0.66))
                            elif _is_narrower_time(a2, a1):
                                rels.append(("GENERALIZES", 0.50))
                                rels.append(("REFINES", 0.82))
                                rels.append(("TEMPORALLY_SPLITS", 0.66))
                        if _is_contradiction_candidate(a1, a2):
                            rels.append(("CONTRADICTS", 0.95))
                        for rel_type, rel_weight in rels:
                            from_id, to_id = int(a1["id"]), int(a2["id"])
                            if rel_type == "REFINES" and _is_narrower_time(a2, a1):
                                from_id, to_id = int(a2["id"]), int(a1["id"])
                            elif rel_type == "GENERALIZES" and _is_narrower_time(a2, a1):
                                from_id, to_id = int(a1["id"]), int(a2["id"])
                            elif rel_type == "GENERALIZES" and _is_narrower_time(a1, a2):
                                from_id, to_id = int(a2["id"]), int(a1["id"])
                            contradiction_signals = 1 if rel_type == "CONTRADICTS" else 0
                            same_subject = bool(a1.get("subject_entity_id") and a1.get("subject_entity_id") == a2.get("subject_entity_id"))
                            same_object = bool(a1.get("object_entity_id") and a1.get("object_entity_id") == a2.get("object_entity_id"))
                            entity_overlap_strength = 1.0 if (same_subject and same_object) else (0.78 if (same_subject or same_object) else 0.0)
                            same_time = _intervals_overlap(a1.get("valid_time_from"), a1.get("valid_time_to"), a2.get("valid_time_from"), a2.get("valid_time_to"))
                            time_overlap_strength = 1.0 if same_time else 0.0
                            same_place = bool((a1.get("place_key") or "").strip() and a1.get("place_key") == a2.get("place_key"))
                            place_overlap_strength = 1.0 if same_place else 0.0
                            evidence_overlap_count = 0
                            if rel_type in {"SUPPORTS", "SAME_SOURCE_POINT"}:
                                evidence_overlap_count += 1
                            if a1.get("source_sentence_id") and a1.get("source_sentence_id") == a2.get("source_sentence_id"):
                                evidence_overlap_count += 1
                            evidence_proximity = min(1.0, 0.35 + 0.30 * evidence_overlap_count)
                            relation_confidence = compute_relation_confidence(
                                relation_weight=rel_weight,
                                relation_type=rel_type,
                                entity_overlap_strength=entity_overlap_strength,
                                time_overlap_strength=time_overlap_strength,
                                place_overlap_strength=place_overlap_strength,
                                evidence_proximity=evidence_proximity,
                                evidence_overlap_count=evidence_overlap_count,
                                assertion_confidence_from=float(a1.get("confidence") or 0.0),
                                assertion_confidence_to=float(a2.get("confidence") or 0.0),
                                contradiction_signals=contradiction_signals,
                            )
                            relation_rows.append(
                                {
                                    "from_assertion_id": from_id,
                                    "to_assertion_id": to_id,
                                    "relation_type": rel_type,
                                    "weight": rel_weight,
                                    "relation_confidence": relation_confidence,
                                    "entity_overlap_strength": entity_overlap_strength,
                                    "time_overlap_strength": time_overlap_strength,
                                    "place_overlap_strength": place_overlap_strength,
                                    "evidence_overlap_count": evidence_overlap_count,
                                    "evidence_proximity": evidence_proximity,
                                    "assertion_confidence_from": float(a1.get("confidence") or 0.0),
                                    "assertion_confidence_to": float(a2.get("confidence") or 0.0),
                                    "contradiction_signals": contradiction_signals,
                                }
                            )
                            if rel_type not in {"REFINES", "GENERALIZES"}:
                                relation_rows.append(
                                    {
                                        "from_assertion_id": int(a2["id"]),
                                        "to_assertion_id": int(a1["id"]),
                                        "relation_type": rel_type,
                                        "weight": rel_weight,
                                        "relation_confidence": relation_confidence,
                                        "entity_overlap_strength": entity_overlap_strength,
                                        "time_overlap_strength": time_overlap_strength,
                                        "place_overlap_strength": place_overlap_strength,
                                        "evidence_overlap_count": evidence_overlap_count,
                                        "evidence_proximity": evidence_proximity,
                                        "assertion_confidence_from": float(a2.get("confidence") or 0.0),
                                        "assertion_confidence_to": float(a1.get("confidence") or 0.0),
                                        "contradiction_signals": contradiction_signals,
                                    }
                                )
                relation_count = self.repo.create_assertion_relations_batch(kb_id=kb_id, rows=relation_rows)
                # Lifecycle státusz újrabecslés relation-háló alapján.
                for assertion in assertion_items:
                    aid = int(assertion["id"])
                    local_rel = [x for x in relation_rows if int(x.get("from_assertion_id") or 0) == aid or int(x.get("to_assertion_id") or 0) == aid]
                    status = determine_assertion_status(
                        confidence=float(assertion.get("confidence") or 0.0),
                        evidence_count=int(assertion.get("evidence_count") or 0),
                        relations=local_rel,
                    )
                    self.repo.update_assertion_status(kb_id=kb_id, assertion_id=aid, status=status)
                    assertion["status"] = status
            except Exception:
                extraction_failed = True

        # Sentence enrichment persist + qdrant payload
        sentence_updates = []
        for sid, meta in sentence_meta.items():
            sentence_updates.append(
                {
                    "id": sid,
                    "entity_ids": sorted(set(int(x) for x in meta.get("entity_ids") or [])),
                    "assertion_ids": sorted(set(int(x) for x in meta.get("assertion_ids") or [])),
                    "mention_ids": sorted(set(int(x) for x in meta.get("mention_ids") or [])),
                    "evidence_assertion_ids": sorted(set(int(x) for x in meta.get("evidence_assertion_ids") or [])),
                    "predicate_hints": sorted(set(str(x) for x in meta.get("predicate_hints") or [] if str(x).strip())),
                    "place_ids": sorted(set(int(x) for x in meta.get("place_ids") or [] if int(x) > 0)),
                    "valid_time_from": meta.get("valid_time_from"),
                    "valid_time_to": meta.get("valid_time_to"),
                    "place_keys": sorted(set(str(x) for x in meta.get("place_keys") or [] if str(x).strip())),
                }
            )
        self.repo.update_sentence_enrichment_batch(kb_id=kb_id, rows=sentence_updates)
        sentence_by_id = {int(x["id"]): x for x in sentence_updates}
        sentence_points = []
        for row in sentence_rows:
            meta = sentence_by_id.get(int(row["id"]), {})
            sentence_points.append(
                {
                    "id": f"sentence-{row['id']}",
                    "text": row["sanitized_text"],
                    "payload": {
                        "sentence_id": int(row["id"]),
                        "kb_uuid": kb_uuid,
                        "kb_id": kb_id,
                        "source_point_id": source_point_id,
                        "source_sentence_id": int(row["id"]),
                        "entity_ids": meta.get("entity_ids") or [],
                        "assertion_ids": meta.get("assertion_ids") or [],
                        "mention_ids": meta.get("mention_ids") or [],
                        "evidence_assertion_ids": meta.get("evidence_assertion_ids") or [],
                        "predicate_hints": meta.get("predicate_hints") or [],
                        "place_ids": meta.get("place_ids") or [],
                        "time_from": meta.get("valid_time_from").isoformat() if meta.get("valid_time_from") else None,
                        "time_to": meta.get("valid_time_to").isoformat() if meta.get("valid_time_to") else None,
                        "valid_time_from": meta.get("valid_time_from").isoformat() if meta.get("valid_time_from") else None,
                        "valid_time_to": meta.get("valid_time_to").isoformat() if meta.get("valid_time_to") else None,
                        "place_keys": meta.get("place_keys") or [],
                        "place_hierarchy_keys": _place_hierarchy_keys_for_records(
                            place_ids=[int(x) for x in (meta.get("place_ids") or []) if int(x) > 0],
                            place_keys=[str(x) for x in (meta.get("place_keys") or []) if str(x).strip()],
                        ),
                        "confidence": None,
                        "strength": None,
                    },
                }
            )
        if sentence_points:
            await self.vector_index.upsert_sentence_points(collection=collection, rows=sentence_points)

        # Chunk enrichment a sentence/assertion metából
        chunk_updates = []
        chunk_points = []
        for row in chunk_rows:
            sentence_ids = [int(x) for x in (row.get("sentence_ids") or []) if isinstance(x, int)]
            chunk_entity_ids: set[int] = set()
            chunk_assertion_ids: set[int] = set()
            chunk_predicates: set[str] = set()
            chunk_places: set[str] = set()
            chunk_place_ids: set[int] = set()
            chunk_mention_ids: set[int] = set()
            chunk_evidence_assertion_ids: set[int] = set()
            chunk_valid_time_from = None
            chunk_valid_time_to = None
            for sid in sentence_ids:
                meta = sentence_by_id.get(sid) or {}
                if not meta:
                    source_meta = sentence_meta.get(
                        sentence_index_to_id.get(sid, -1),
                        {},
                    )
                    meta = source_meta
                chunk_entity_ids.update(int(x) for x in (meta.get("entity_ids") or []))
                chunk_assertion_ids.update(int(x) for x in (meta.get("assertion_ids") or []))
                chunk_mention_ids.update(int(x) for x in (meta.get("mention_ids") or []) if int(x) > 0)
                chunk_evidence_assertion_ids.update(int(x) for x in (meta.get("evidence_assertion_ids") or []) if int(x) > 0)
                chunk_predicates.update(str(x) for x in (meta.get("predicate_hints") or []) if str(x).strip())
                chunk_places.update(str(x) for x in (meta.get("place_keys") or []) if str(x).strip())
                chunk_place_ids.update(int(x) for x in (meta.get("place_ids") or []) if int(x) > 0)
                s_from = meta.get("valid_time_from") or meta.get("time_from")
                s_to = meta.get("valid_time_to") or meta.get("time_to")
                if s_from is not None:
                    chunk_valid_time_from = s_from if chunk_valid_time_from is None else min(chunk_valid_time_from, s_from)
                if s_to is not None:
                    chunk_valid_time_to = s_to if chunk_valid_time_to is None else max(chunk_valid_time_to, s_to)
            chunk_updates.append(
                {
                    "id": int(row["id"]),
                    "assertion_ids": sorted(chunk_assertion_ids),
                    "entity_ids": sorted(chunk_entity_ids),
                    "predicate_hints": sorted(chunk_predicates),
                    "place_ids": sorted(chunk_place_ids),
                    "valid_time_from": chunk_valid_time_from,
                    "valid_time_to": chunk_valid_time_to,
                    "place_keys": sorted(chunk_places),
                }
            )
            chunk_points.append(
                {
                    "id": f"chunk-{row['id']}",
                    "text": row["text"],
                    "payload": {
                        "chunk_id": int(row["id"]),
                        "kb_uuid": kb_uuid,
                        "kb_id": kb_id,
                        "source_point_id": source_point_id,
                        "source_sentence_id": None,
                        "sentence_ids": sentence_ids,
                        "assertion_ids": sorted(chunk_assertion_ids),
                        "mention_ids": sorted(chunk_mention_ids),
                        "evidence_assertion_ids": sorted(chunk_evidence_assertion_ids),
                        "entity_ids": sorted(chunk_entity_ids),
                        "predicate_hints": sorted(chunk_predicates),
                        "place_ids": sorted(chunk_place_ids),
                        "time_from": chunk_valid_time_from.isoformat() if chunk_valid_time_from else None,
                        "time_to": chunk_valid_time_to.isoformat() if chunk_valid_time_to else None,
                        "valid_time_from": chunk_valid_time_from.isoformat() if chunk_valid_time_from else None,
                        "valid_time_to": chunk_valid_time_to.isoformat() if chunk_valid_time_to else None,
                        "place_keys": sorted(chunk_places),
                        "place_hierarchy_keys": _place_hierarchy_keys_for_records(
                            place_ids=sorted(chunk_place_ids),
                            place_keys=sorted(chunk_places),
                        ),
                        "token_count": int(row.get("token_count") or 0),
                        "confidence": None,
                        "strength": None,
                    },
                }
            )
        self.repo.update_structural_chunk_enrichment_batch(kb_id=kb_id, rows=chunk_updates)
        if chunk_points:
            await self.vector_index.upsert_structural_chunk_points(collection=collection, rows=chunk_points)

        return {
            "sentence_count": len(sentence_rows),
            "chunk_count": len(chunk_rows),
            "entity_count": entity_count,
            "mention_count": mention_count,
            "assertion_count": assertion_count,
            "evidence_count": evidence_count,
            "relation_count": relation_count,
            "extraction_failed": extraction_failed,
            "indexed_at": _utcnow_naive().isoformat(),
        }
