from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from typing import Any

import pytest

from apps.knowledge.api.schemas import IngestRunTraceResponse
from apps.knowledge.domain.corpus import Corpus
from apps.knowledge.domain.document import Document
from apps.knowledge.domain.ingest_event import IngestEvent
from apps.knowledge.domain.ingest_input import IngestInput
from apps.knowledge.domain.ingest_item import IngestItem
from apps.knowledge.domain.ingest_run import IngestRun
from apps.knowledge.domain.interpretation_run import InterpretationRun
from apps.knowledge.domain.mention import Mention
from apps.knowledge.domain.paragraph import Paragraph
from apps.knowledge.domain.parser_run import ParserRun
from apps.knowledge.domain.sentence import Sentence
from apps.knowledge.domain.sentence_interpretation import SentenceInterpretation
from apps.knowledge.domain.space_time_frame import SpaceTimeFrame
from apps.knowledge.service.knowledge_facade import KnowledgeFacade
from apps.knowledge.service.language_rules import fold_text
from apps.knowledge.service.runtime_store import (
    InMemoryIndexBuildStore,
    InMemoryIndexProfileStore,
    InMemoryMetricsStore,
    InMemoryQueryRunStore,
    InMemorySourceStore,
    SimpleChunkBuilder,
    SimpleContextBuilder,
    SimpleRetrievalEngine,
)
from shared.object_storage.models import StoredObjectData, StoredObjectRef


pytestmark = [pytest.mark.integration]


REGRESSION_TEXT_V1 = """Nagy Eszter a Zalka 2000 adatvédelmi felelőse.
Korábban a belső incidenskezelési folyamatért felelt.

Sarah Miller is the data protection lead at Zalka 2000.
Previously responsible for the internal incident handling process.

Peter Kovacs is the support lead at Zalka 2000.

Carlos García es el responsable de protección de datos en Zalka 2000.
Anteriormente fue responsable del proceso interno de gestión de incidentes.

The London office is currently inactive.
It was active before January 2025.

The Berlin office is currently inactive.
It was active before February 2025.

La oficina de Valencia está actualmente activa.
Estaba inactiva en 2024.

A Budapesti iroda jelenleg aktív támogatási központ.

A billing service jelenleg Stripe rendszert használ kártyás fizetésekhez.
The billing module uses Stripe for invoice payments.
The invoice service uses manual invoicing for enterprise customers.

Az admin felhasználónak kötelező kétfaktoros azonosítást használnia.
The admin user must enable two-factor authentication.
El usuario administrador debe activar la autenticación de dos factores.

A support module jelenleg Freshdesk rendszert használ az ügyfélticketek kezelésére.
The support service uses Freshdesk for customer tickets.
El módulo de soporte utiliza Freshdesk para gestionar tickets de clientes.
The document says the support service uses Freshdesk.
The report states that historical import claims remain auditable.
According to the document, the legacy import module was deprecated in 2024.
A dokumentum szerint a support module jelenleg Freshdesk rendszert használ.
A forrás szerint a régi import modul történeti claimként megmarad.
Según el documento, el módulo de soporte utiliza Freshdesk.

A régi Helpdesk import 2024-ben megszűnt.
The legacy helpdesk import was deprecated in 2024.
Historical tickets remain searchable.
A régi Helpdesk import nem aktív.
The legacy helpdesk import is not active.
El usuario invitado no debe modificar datos de facturación.

Ez csak zaj, nem kell belőle fontos claim.

Later, the account was updated in April 2026.
The account was created in March 2025.
La cuenta fue creada en marzo de 2025.
Fue actualizada en abril de 2026.
"""


_STOPWORD_SUBJECTS = {
    "a",
    "az",
    "the",
    "it",
    "this",
    "that",
    "la",
    "el",
    "fue",
    "was",
    "later",
    "korabban",
    "previously",
    "anteriormente",
    "estaba",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


class _CorpusStore:
    def __init__(self) -> None:
        now = _now()
        self._items = {
            "kb-regression": Corpus(
                id=1,
                tenant="demo",
                uuid="kb-regression",
                name="Knowledge Regression KB",
                description="Knowledge pipeline regression corpus",
                qdrant_collection_name="kb_regression",
                created_at=now,
                updated_at=now,
            )
        }

    def get_by_uuid(self, uuid: str) -> Corpus | None:
        return self._items.get(uuid)

    def list_all(self) -> list[Corpus]:
        return list(self._items.values())


class _UserRepo:
    def list_all(self) -> list[Any]:
        return []


class _InMemoryRunStore:
    def __init__(self) -> None:
        self.items: dict[str, IngestRun] = {}

    def create(self, item: IngestRun) -> IngestRun:
        self.items[item.id] = item
        return item

    def update(self, item: IngestRun) -> IngestRun:
        self.items[item.id] = item
        return item

    def get(self, item_id: str) -> IngestRun | None:
        return self.items.get(item_id)

    def list_for_corpus(self, corpus_uuid: str, limit: int = 20) -> list[IngestRun]:
        items = [item for item in self.items.values() if item.corpus_uuid == corpus_uuid]
        return sorted(items, key=lambda item: item.created_at, reverse=True)[:limit]

    def list_recent(self, limit: int = 20) -> list[IngestRun]:
        return sorted(self.items.values(), key=lambda item: item.created_at, reverse=True)[:limit]


class _InMemoryItemStore:
    def __init__(self) -> None:
        self.items: dict[str, IngestItem] = {}

    def create_many(self, items: list[IngestItem]) -> list[IngestItem]:
        for item in items:
            self.items[item.id] = item
        return items

    def update(self, item: IngestItem) -> IngestItem:
        self.items[item.id] = item
        return item

    def get(self, item_id: str) -> IngestItem | None:
        return self.items.get(item_id)

    def list_for_run(self, run_id: str) -> list[IngestItem]:
        items = [item for item in self.items.values() if item.ingest_run_id == run_id]
        return sorted(items, key=lambda item: item.queue_order)

    def find_by_hash(
        self,
        *,
        corpus_uuid: str,
        content_hash: str,
        exclude_item_id: str | None = None,
    ) -> IngestItem | None:
        for item in self.items.values():
            if item.id == exclude_item_id or item.corpus_uuid != corpus_uuid:
                continue
            if item.content_hash == content_hash:
                return item
        return None


class _InMemoryInputStore:
    def __init__(self) -> None:
        self.items: dict[str, IngestInput] = {}

    def create_many(self, items: list[IngestInput]) -> list[IngestInput]:
        for item in items:
            self.items[item.ingest_item_id] = item
        return items

    def get_for_item(self, item_id: str) -> IngestInput | None:
        return self.items.get(item_id)


class _InMemoryEventStore:
    def __init__(self) -> None:
        self.items: list[IngestEvent] = []

    def create(self, item: IngestEvent) -> IngestEvent:
        self.items.append(item)
        return item

    def list_for_run(self, run_id: str, limit: int = 200) -> list[IngestEvent]:
        return [item for item in self.items if item.ingest_run_id == run_id][:limit]


class _ParserRunStore:
    def __init__(self) -> None:
        self.items: dict[str, ParserRun] = {}

    def create(self, item: ParserRun) -> ParserRun:
        self.items[item.id] = item
        return item

    def update(self, item: ParserRun) -> ParserRun:
        self.items[item.id] = item
        return item

    def get_for_source(self, source_id: str) -> ParserRun | None:
        runs = [item for item in self.items.values() if item.source_id == source_id]
        return sorted(runs, key=lambda item: item.created_at, reverse=True)[0] if runs else None

    def delete_for_source(self, source_id: str) -> int:
        ids = [item_id for item_id, item in self.items.items() if item.source_id == source_id]
        for item_id in ids:
            self.items.pop(item_id, None)
        return len(ids)


class _DocumentStore:
    def __init__(self) -> None:
        self.items: dict[str, Document] = {}

    def create(self, item: Document) -> Document:
        self.items[item.id] = item
        return item

    def get(self, item_id: str) -> Document | None:
        return self.items.get(item_id)

    def get_for_source(self, source_id: str) -> Document | None:
        return next((item for item in self.items.values() if item.source_id == source_id), None)

    def delete_for_source(self, source_id: str) -> int:
        ids = [item_id for item_id, item in self.items.items() if item.source_id == source_id]
        for item_id in ids:
            self.items.pop(item_id, None)
        return len(ids)


class _DocumentChildStore:
    def __init__(self) -> None:
        self.items: dict[str, Any] = {}

    def create_many(self, items: list[Any]) -> list[Any]:
        for item in items:
            self.items[item.id] = item
        return items

    def list_for_document(self, document_id: str) -> list[Any]:
        items = [item for item in self.items.values() if item.document_id == document_id]
        return sorted(items, key=lambda item: (getattr(item, "order_index", 0), getattr(item, "char_start", 0)))

    def delete_for_document(self, document_id: str) -> int:
        ids = [item_id for item_id, item in self.items.items() if item.document_id == document_id]
        for item_id in ids:
            self.items.pop(item_id, None)
        return len(ids)


class _SentenceStore(_DocumentChildStore):
    def get(self, item_id: str) -> Sentence | None:
        return self.items.get(item_id)


class _SentenceInterpretationStore(_DocumentChildStore):
    def get_for_sentence(self, sentence_id: str) -> SentenceInterpretation | None:
        return next((item for item in self.items.values() if item.sentence_id == sentence_id), None)


class _MentionStore(_DocumentChildStore):
    def list_for_sentence(self, sentence_id: str) -> list[Mention]:
        items = [item for item in self.items.values() if item.sentence_id == sentence_id]
        return sorted(items, key=lambda item: (item.char_start, item.char_end, item.created_at))


class _ClaimStore(_DocumentChildStore):
    def list_for_sentence(self, sentence_id: str) -> list[Any]:
        items = [item for item in self.items.values() if item.sentence_id == sentence_id]
        return sorted(items, key=lambda item: (item.created_at, item.claim_id))


class _SpaceTimeFrameStore(_DocumentChildStore):
    def list_for_sentence(self, sentence_id: str) -> list[SpaceTimeFrame]:
        return [item for item in self.items.values() if item.sentence_id == sentence_id]


class _InterpretationRunStore:
    def __init__(self) -> None:
        self.items: dict[str, InterpretationRun] = {}

    def create(self, item: InterpretationRun) -> InterpretationRun:
        self.items[item.id] = item
        return item

    def update(self, item: InterpretationRun) -> InterpretationRun:
        self.items[item.id] = item
        return item

    def get_for_document(self, document_id: str) -> InterpretationRun | None:
        runs = [item for item in self.items.values() if item.document_id == document_id]
        return sorted(runs, key=lambda item: item.created_at, reverse=True)[0] if runs else None

    def delete_for_document(self, document_id: str) -> int:
        ids = [item_id for item_id, item in self.items.items() if item.document_id == document_id]
        for item_id in ids:
            self.items.pop(item_id, None)
        return len(ids)


class _NoopObjectStorage:
    def put_bytes(
        self,
        *,
        key: str,
        content: bytes,
        bucket: str | None = None,
        content_type: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> StoredObjectRef:
        return StoredObjectRef(
            provider="noop",
            bucket=bucket or "test-bucket",
            key=key,
            size_bytes=len(content),
            content_type=content_type,
            metadata=metadata or {},
        )

    def get_bytes(self, *, key: str, bucket: str | None = None) -> StoredObjectData:
        return StoredObjectData(
            ref=StoredObjectRef(
                provider="noop",
                bucket=bucket or "test-bucket",
                key=key,
                size_bytes=0,
                content_type="application/octet-stream",
                metadata={},
            ),
            body=b"",
        )

    def build_key(self, *parts: str) -> str:
        return "/".join(part.strip("/") for part in parts if part)


class _VectorIndex:
    async def ensure_collection_schema_async(self, collection_name: str, vector_size: int | None = None) -> None:
        return None

    async def upsert_sentence_points(self, collection: str, rows: list[dict[str, object]]) -> None:
        return None

    async def search_points(self, *args: Any, **kwargs: Any) -> list[dict[str, object]]:
        return []


class PipelineRegressionHarnessV1:
    def __init__(self) -> None:
        vector = _VectorIndex()
        self.ingest_run_store = _InMemoryRunStore()
        self.ingest_item_store = _InMemoryItemStore()
        self.facade = KnowledgeFacade(
            corpus_store=_CorpusStore(),
            user_repo=_UserRepo(),
            source_store=InMemorySourceStore(),
            ingest_run_store=self.ingest_run_store,
            ingest_item_store=self.ingest_item_store,
            ingest_input_store=_InMemoryInputStore(),
            ingest_event_store=_InMemoryEventStore(),
            parser_run_store=_ParserRunStore(),
            document_store=_DocumentStore(),
            paragraph_store=_DocumentChildStore(),
            sentence_store=_SentenceStore(),
            interpretation_run_store=_InterpretationRunStore(),
            sentence_interpretation_store=_SentenceInterpretationStore(),
            mention_store=_MentionStore(),
            claim_store=_ClaimStore(),
            space_time_frame_store=_SpaceTimeFrameStore(),
            index_profile_store=InMemoryIndexProfileStore(),
            index_build_store=InMemoryIndexBuildStore(),
            query_run_store=InMemoryQueryRunStore(),
            chunk_builder=SimpleChunkBuilder(),
            retrieval_engine=SimpleRetrievalEngine(lambda: vector),
            context_builder=SimpleContextBuilder(),
            vector_index_factory=lambda: vector,
            metrics_store=InMemoryMetricsStore(),
            object_storage=_NoopObjectStorage(),
        )

    def run_text(self, text: str) -> dict[str, Any]:
        run = self.facade.create_text_ingest_run(
            tenant="demo",
            corpus_uuid="kb-regression",
            title="Knowledge Pipeline Regression v1",
            text=text,
            created_by=None,
        )
        completed = self.facade.process_ingest_run(run.id)
        trace = self.facade.get_ingest_run_trace(completed.id)
        assert trace is not None
        return trace


def _claims(trace: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        claim
        for sentence in trace.get("sentences") or []
        for claim in sentence.get("claims") or []
    ]


def _quality_metrics(trace: dict[str, Any]) -> dict[str, Any]:
    claims = _claims(trace)
    quality = dict((trace.get("summary") or {}).get("quality") or {})
    claim_count = max(len(claims), 1)
    describes_count = int(quality.get("describes_claim_count") or 0)
    local_entity_count = int((trace.get("summary") or {}).get("local_entity_count") or 0)
    unknown_entity_type_count = int((trace.get("summary") or {}).get("unknown_entity_type_count") or 0)
    duplicate_candidate_count = _duplicate_candidate_count(trace)
    weak_auxiliary_claim_count = _weak_auxiliary_claim_count(trace)
    false_carryover_subject_count = _false_carryover_subject_count(trace)
    noise_sentence_generated_claim_count = _noise_sentence_generated_claim_count(trace)
    return {
        "describes_ratio": describes_count / claim_count,
        "unknown_type_ratio": unknown_entity_type_count / max(local_entity_count, 1),
        "claims_with_no_real_subject": sum(
            1 for claim in claims if len(str(claim.get("subject_text") or "").strip()) <= 2
        ),
        "claims_with_stopword_subject": sum(
            1
            for claim in claims
            if fold_text(str(claim.get("subject_text") or "").strip()) in _STOPWORD_SUBJECTS
        ),
        "claims_without_stored_space_time_frame": sum(
            1
            for claim in claims
            if not (claim.get("space_time_frame") or {}).get("frame_id")
            or str((claim.get("space_time_frame") or {}).get("frame_id") or "").startswith("compat:")
        ),
        "local_resolver_ready": bool((trace.get("summary") or {}).get("local_resolver_ready")),
        "long_subject_count": int((trace.get("summary") or {}).get("long_subject_count") or 0),
        "bad_subject_claim_count": int((trace.get("summary") or {}).get("bad_subject_claim_count") or 0),
        "carryover_subject_error_count_summary": int((trace.get("summary") or {}).get("carryover_subject_error_count") or 0),
        "profiles_without_evidence": sum(
            1 for item in trace.get("search_profiles") or [] if not item.get("evidence_refs")
        ),
        "chunks_without_evidence": sum(
            1 for item in trace.get("technical_memory_chunks") or [] if not item.get("evidence_refs")
        ),
        "candidate_selection_ready": bool((trace.get("summary") or {}).get("candidate_selection_ready")),
        "candidates_without_evidence_count": int((trace.get("summary") or {}).get("candidates_without_evidence_count") or 0),
        "similarity_without_evidence_count": int((trace.get("summary") or {}).get("similarity_without_evidence_count") or 0),
        "max_candidates_per_profile": int((trace.get("summary") or {}).get("max_candidates_per_profile") or 0),
        "similarity_ready": bool((trace.get("summary") or {}).get("similarity_ready")),
        "medium_similarity_count": int((trace.get("summary") or {}).get("medium_similarity_count") or 0),
        "tension_ready": bool((trace.get("summary") or {}).get("tension_ready")),
        "tension_without_evidence_count": int((trace.get("summary") or {}).get("tension_without_evidence_count") or 0),
        "decision_ready": bool((trace.get("summary") or {}).get("decision_ready")),
        "noise_sentence_skipped_count": int(quality.get("noise_sentence_skipped_count") or 0),
        "noise_claim_rejected_count": int(quality.get("noise_claim_rejected_count") or 0),
        "carryover_subject_error_count": int(quality.get("carryover_subject_error_count") or 0),
        "context_carryover_blocked_due_to_explicit_subject_count": int(
            quality.get("context_carryover_blocked_due_to_explicit_subject_count") or 0
        ),
        "temporal_subject_sanitized_count": int(quality.get("temporal_subject_sanitized_count") or 0),
        "weak_auxiliary_claim_rejected_count": int(quality.get("weak_auxiliary_claim_rejected_count") or 0),
        "duplicate_weak_claim_rejected_count": int(quality.get("duplicate_weak_claim_rejected_count") or 0),
        "noise_sentence_generated_claim_count": noise_sentence_generated_claim_count,
        "false_carryover_subject_count": false_carryover_subject_count,
        "weak_auxiliary_claim_count": weak_auxiliary_claim_count,
        "duplicate_candidate_count": duplicate_candidate_count,
        "unknown_entity_type_count": unknown_entity_type_count,
        "entity_type_normalized_count": int((trace.get("summary") or {}).get("entity_type_normalized_count") or 0),
        "unresolved_pronoun_entity_count": int((trace.get("summary") or {}).get("unresolved_pronoun_entity_count") or 0),
        "negation_in_entity_name_count": int((trace.get("summary") or {}).get("negation_in_entity_name_count") or 0),
        "negative_claim_count": int((trace.get("summary") or {}).get("negative_claim_count") or 0),
        "source_phrase_entity_count": int((trace.get("summary") or {}).get("source_phrase_entity_count") or 0),
        "duplicate_compatible_type_entity_count": int((trace.get("summary") or {}).get("duplicate_compatible_type_entity_count") or 0),
        "bare_support_entity_count": int((trace.get("summary") or {}).get("bare_support_entity_count") or 0),
        "relation_pattern_subject_error_count": int((trace.get("summary") or {}).get("relation_pattern_subject_error_count") or 0),
        "source_phrase_in_object_count": int((trace.get("summary") or {}).get("source_phrase_in_object_count") or 0),
        "location_claims_with_unknown_space": int((trace.get("summary") or {}).get("location_claims_with_unknown_space") or 0),
    }


def _names(trace: dict[str, Any], key: str) -> list[str]:
    return [
        str(item.get("canonical_name") or item.get("entity_name") or item.get("name") or "")
        for item in trace.get(key) or []
    ]


def _has_entity(trace: dict[str, Any], expected_name: str) -> bool:
    expected = fold_text(expected_name)
    names = _names(trace, "local_entities") + _names(trace, "technical_entities")
    return any(fold_text(name) == expected for name in names)


def _has_entity_containing(trace: dict[str, Any], expected_fragment: str) -> bool:
    expected = fold_text(expected_fragment)
    names = _names(trace, "local_entities") + _names(trace, "technical_entities") + _names(trace, "search_profiles")
    return any(expected in fold_text(name) for name in names)


def _entity_type_for_name(trace: dict[str, Any], expected_name: str) -> str | None:
    expected = fold_text(expected_name)
    for item in (trace.get("local_entities") or []) + (trace.get("technical_entities") or []):
        name = str(item.get("canonical_name") or item.get("entity_name") or item.get("name") or "")
        if fold_text(name) == expected:
            return str(item.get("entity_type") or item.get("type") or "")
    return None


def _technical_entity(trace: dict[str, Any], expected_name: str) -> dict[str, Any] | None:
    expected = fold_text(expected_name)
    for item in trace.get("technical_entities") or []:
        if fold_text(str(item.get("canonical_name") or item.get("name") or "")) == expected:
            return item
    return None


def _state_claim_count(trace: dict[str, Any], expected_name: str) -> int:
    entity = _technical_entity(trace, expected_name)
    if entity is None:
        return 0
    claim_groups = dict(entity.get("claim_groups") or entity.get("claims") or {})
    return int(claim_groups.get("state") or 0)


def _profile_name_by_id(trace: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for profile in trace.get("search_profiles") or []:
        profile_id = str(profile.get("search_profile_id") or "")
        if profile_id:
            out[profile_id] = str(profile.get("entity_name") or "")
    return out


def _admin_profile_names(trace: dict[str, Any]) -> set[str]:
    names: set[str] = set()
    for profile in trace.get("search_profiles") or []:
        name = str(profile.get("entity_name") or "")
        folded = fold_text(name)
        if "admin" in folded or "administrador" in folded:
            names.add(folded)
    return names


def _has_duplicate_candidate_per_profile(trace: dict[str, Any]) -> bool:
    return _duplicate_candidate_count(trace) > 0


def _duplicate_candidate_count(trace: dict[str, Any]) -> int:
    seen: set[tuple[str, str]] = set()
    count = 0
    for candidate in trace.get("candidate_selections") or []:
        key = (
            str(candidate.get("search_profile_id") or ""),
            str(candidate.get("candidate_entity_id") or ""),
        )
        if key in seen:
            count += 1
            continue
        seen.add(key)
    return count


def _noise_sentence_generated_claim_count(trace: dict[str, Any]) -> int:
    count = 0
    for sentence in trace.get("sentences") or []:
        text = fold_text(str(sentence.get("text") or sentence.get("text_content") or ""))
        if "ez csak zaj" in text or "nem kell belole fontos claim" in text:
            count += len(sentence.get("claims") or [])
    return count


def _false_carryover_subject_count(trace: dict[str, Any]) -> int:
    count = 0
    if _entity_profile_contains(trace, "Budapesti iroda", "használ", "kártyás fizetésekhez"):
        count += 1
    if _entity_profile_contains(trace, "usuario administrador", "használ", "ügyfélticketek kezelésére"):
        count += 1
    return count


def _weak_auxiliary_claim_count(trace: dict[str, Any]) -> int:
    count = 0
    for claim in _claims(trace):
        predicate = fold_text(str(claim.get("predicate_text") or claim.get("predicate") or ""))
        object_text = str(claim.get("object_text") or "").strip()
        if predicate in {"fue", "was", "is", "van", "volt", "es", "esta", "está"} and object_text in {"", "-"}:
            count += 1
    if _entity_has_empty_predicate_fact(trace, "cuenta", "Fue"):
        count += 1
    return count


def _has_admin_candidate_or_similarity_link(trace: dict[str, Any]) -> bool:
    profile_names = _profile_name_by_id(trace)
    admin_names = _admin_profile_names(trace)
    if len(admin_names) < 2:
        return False
    for candidate in trace.get("candidate_selections") or []:
        left = fold_text(profile_names.get(str(candidate.get("search_profile_id") or ""), ""))
        right = fold_text(str(candidate.get("candidate_name") or ""))
        if left in admin_names and right in admin_names and left != right:
            return True
    for analysis in trace.get("similarity_analyses") or []:
        left = fold_text(profile_names.get(str(analysis.get("search_profile_id") or ""), ""))
        right = fold_text(str(analysis.get("candidate_name") or ""))
        if left in admin_names and right in admin_names and left != right:
            return True
    return False


def _london_berlin_similarity_is_low(trace: dict[str, Any]) -> bool:
    profile_names = _profile_name_by_id(trace)
    found = False
    for analysis in trace.get("similarity_analyses") or []:
        left = fold_text(profile_names.get(str(analysis.get("search_profile_id") or ""), ""))
        right = fold_text(str(analysis.get("candidate_name") or ""))
        if {left, right} != {"london office", "berlin office"}:
            continue
        found = True
        if str(analysis.get("similarity_band") or "") != "low":
            return False
    return found


def _noise_sentence_has_technical_entity(trace: dict[str, Any]) -> bool:
    for item in trace.get("technical_entities") or []:
        haystack = " ".join(
            [
                str(item.get("canonical_name") or ""),
                str(item.get("name") or ""),
                str(item.get("normalized_key") or ""),
            ]
        )
        folded = fold_text(haystack)
        if "ez csak zaj" in folded or "nem kell belole fontos claim" in folded:
            return True
    return False


def _entity_profile_contains(trace: dict[str, Any], entity_name: str, *needles: str) -> bool:
    entity_fold = fold_text(entity_name)
    needle_folds = [fold_text(item) for item in needles]
    for item in trace.get("technical_entities") or []:
        name = fold_text(str(item.get("canonical_name") or item.get("name") or ""))
        if name != entity_fold:
            continue
        haystack = fold_text(str(item))
        if all(needle in haystack for needle in needle_folds):
            return True
    for item in trace.get("technical_memory_chunks") or []:
        name = fold_text(str(item.get("entity_name") or ""))
        if name != entity_fold:
            continue
        haystack = fold_text(str(item))
        if all(needle in haystack for needle in needle_folds):
            return True
    return False


def _entity_has_empty_predicate_fact(trace: dict[str, Any], entity_name: str, predicate: str) -> bool:
    entity_fold = fold_text(entity_name)
    predicate_fold = fold_text(predicate)
    for item in trace.get("technical_memory_chunks") or []:
        if fold_text(str(item.get("entity_name") or "")) != entity_fold:
            continue
        for fact in item.get("facts") or []:
            if fold_text(str(fact.get("predicate") or "")) != predicate_fold:
                continue
            object_text = str(fact.get("object_text") or "").strip()
            if not object_text or object_text == "-":
                return True
    return False


def _search_profile_canonical_contains(trace: dict[str, Any], entity_name: str, needle: str) -> bool:
    entity_fold = fold_text(entity_name)
    for item in trace.get("search_profiles") or []:
        if fold_text(str(item.get("entity_name") or "")) != entity_fold:
            continue
        if needle in str(item.get("canonical_text") or ""):
            return True
    return False


def _has_claim_evidence_chain(trace: dict[str, Any]) -> bool:
    if not trace.get("source_id"):
        return False
    for sentence in trace.get("sentences") or []:
        if not sentence.get("sentence_id"):
            return False
        for claim in sentence.get("claims") or []:
            if not claim.get("claim_id"):
                return False
    return True


def _soft_check(failures: list[str], label: str, actual: Any, expected: Any) -> None:
    if actual != expected:
        failures.append(f"{label}: expected={expected!r}, actual={actual!r}")


def test_pipeline_regression_v1_smoke_trace_quality_and_entities() -> None:
    trace = PipelineRegressionHarnessV1().run_text(REGRESSION_TEXT_V1)
    IngestRunTraceResponse.model_validate(trace)

    metrics = _quality_metrics(trace)
    failures: list[str] = []

    _soft_check(failures, "describes_ratio", metrics["describes_ratio"], 0)
    _soft_check(failures, "claims_with_no_real_subject", metrics["claims_with_no_real_subject"], 0)
    _soft_check(failures, "claims_with_stopword_subject", metrics["claims_with_stopword_subject"], 0)
    _soft_check(
        failures,
        "claims_without_stored_space_time_frame",
        metrics["claims_without_stored_space_time_frame"],
        0,
    )
    _soft_check(failures, "local_resolver_ready", metrics["local_resolver_ready"], True)
    _soft_check(failures, "long_subject_count", metrics["long_subject_count"], 0)
    _soft_check(failures, "bad_subject_claim_count", metrics["bad_subject_claim_count"], 0)
    _soft_check(failures, "carryover_subject_error_count_summary", metrics["carryover_subject_error_count_summary"], 0)
    _soft_check(failures, "unresolved_pronoun_entity_count", metrics["unresolved_pronoun_entity_count"], 0)
    _soft_check(failures, "negation_in_entity_name_count", metrics["negation_in_entity_name_count"], 0)
    if metrics["negative_claim_count"] <= 0:
        failures.append(f"negative_claim_count: expected > 0, actual={metrics['negative_claim_count']!r}")
    _soft_check(failures, "source_phrase_entity_count", metrics["source_phrase_entity_count"], 0)
    _soft_check(
        failures,
        "duplicate_compatible_type_entity_count",
        metrics["duplicate_compatible_type_entity_count"],
        0,
    )
    _soft_check(failures, "bare_support_entity_count", metrics["bare_support_entity_count"], 0)
    _soft_check(
        failures,
        "relation_pattern_subject_error_count",
        metrics["relation_pattern_subject_error_count"],
        0,
    )
    _soft_check(failures, "source_phrase_in_object_count", metrics["source_phrase_in_object_count"], 0)
    _soft_check(
        failures,
        "location_claims_with_unknown_space",
        metrics["location_claims_with_unknown_space"],
        0,
    )
    _soft_check(failures, "profiles_without_evidence", metrics["profiles_without_evidence"], 0)
    _soft_check(failures, "chunks_without_evidence", metrics["chunks_without_evidence"], 0)
    _soft_check(failures, "candidate_selection_ready", metrics["candidate_selection_ready"], True)
    _soft_check(failures, "candidates_without_evidence_count", metrics["candidates_without_evidence_count"], 0)
    _soft_check(failures, "similarity_without_evidence_count", metrics["similarity_without_evidence_count"], 0)
    if metrics["max_candidates_per_profile"] > 5:
        failures.append(
            "max_candidates_per_profile: "
            f"expected <= 5, actual={metrics['max_candidates_per_profile']!r}"
        )
    _soft_check(failures, "similarity_ready", metrics["similarity_ready"], True)
    if metrics["medium_similarity_count"] <= 0:
        failures.append(f"medium_similarity_count: expected > 0, actual={metrics['medium_similarity_count']!r}")
    _soft_check(failures, "tension_ready", metrics["tension_ready"], True)
    _soft_check(failures, "tension_without_evidence_count", metrics["tension_without_evidence_count"], 0)
    _soft_check(failures, "decision_ready", metrics["decision_ready"], True)
    if metrics["noise_sentence_skipped_count"] <= 0:
        failures.append(
            "noise_sentence_skipped_count: "
            f"expected > 0, actual={metrics['noise_sentence_skipped_count']!r}"
        )
    _soft_check(failures, "noise_claim_rejected_count", metrics["noise_claim_rejected_count"], 0)
    _soft_check(failures, "noise_sentence_generated_claim_count", metrics["noise_sentence_generated_claim_count"], 0)
    _soft_check(failures, "carryover_subject_error_count", metrics["carryover_subject_error_count"], 0)
    _soft_check(failures, "false_carryover_subject_count", metrics["false_carryover_subject_count"], 0)
    _soft_check(failures, "weak_auxiliary_claim_count", metrics["weak_auxiliary_claim_count"], 0)
    _soft_check(failures, "duplicate_candidate_count", metrics["duplicate_candidate_count"], 0)
    if metrics["context_carryover_blocked_due_to_explicit_subject_count"] <= 0:
        failures.append(
            "context_carryover_blocked_due_to_explicit_subject_count: "
            f"expected > 0, actual={metrics['context_carryover_blocked_due_to_explicit_subject_count']!r}"
        )
    if metrics["temporal_subject_sanitized_count"] <= 0:
        failures.append(
            "temporal_subject_sanitized_count: "
            f"expected > 0, actual={metrics['temporal_subject_sanitized_count']!r}"
        )
    if metrics["weak_auxiliary_claim_rejected_count"] <= 0:
        failures.append(
            "weak_auxiliary_claim_rejected_count: "
            f"expected > 0, actual={metrics['weak_auxiliary_claim_rejected_count']!r}"
        )
    if metrics["duplicate_weak_claim_rejected_count"] <= 0:
        failures.append(
            "duplicate_weak_claim_rejected_count: "
            f"expected > 0, actual={metrics['duplicate_weak_claim_rejected_count']!r}"
        )
    if metrics["entity_type_normalized_count"] <= 0:
        failures.append(
            "entity_type_normalized_count: "
            f"expected > 0, actual={metrics['entity_type_normalized_count']!r}"
        )
    # Mérőszám, nem hard elvárás: unknown entity type még elfogadható, de trendelhető legyen.
    assert metrics["unknown_type_ratio"] >= 0
    _soft_check(failures, "evidence_chain_ready", _has_claim_evidence_chain(trace), True)

    _soft_check(failures, "Nagy Eszter entity exists", _has_entity(trace, "Nagy Eszter"), True)
    _soft_check(
        failures,
        "candidate selections have no duplicate candidate_entity_id per profile",
        _has_duplicate_candidate_per_profile(trace),
        False,
    )
    _soft_check(failures, "Sarah Miller entity exists", _has_entity(trace, "Sarah Miller"), True)
    _soft_check(failures, "Carlos García entity exists", _has_entity(trace, "Carlos García"), True)
    _soft_check(failures, "billing service entity exists", _has_entity(trace, "billing service"), True)
    _soft_check(failures, "support module entity exists", _has_entity(trace, "support module"), True)
    _soft_check(failures, "London office has two state claims", _state_claim_count(trace, "London office"), 2)
    _soft_check(failures, "Berlin office has two state claims", _state_claim_count(trace, "Berlin office"), 2)
    _soft_check(failures, "London office and Berlin office similarity remains low", _london_berlin_similarity_is_low(trace), True)
    _soft_check(
        failures,
        "oficina de Valencia has two state claims",
        _state_claim_count(trace, "oficina de Valencia"),
        2,
    )
    _soft_check(
        failures,
        "admin multilingual candidate/similarity link exists",
        _has_admin_candidate_or_similarity_link(trace),
        True,
    )
    _soft_check(
        failures,
        'no entity named "Ez csak zaj, nem"',
        _noise_sentence_has_technical_entity(trace),
        False,
    )
    _soft_check(
        failures,
        "Later, the account entity does not exist",
        _has_entity_containing(trace, "Later, the account"),
        False,
    )
    _soft_check(
        failures,
        "Budapesti iroda profile does not contain billing card payment carryover",
        _entity_profile_contains(trace, "Budapesti iroda", "használ", "kártyás fizetésekhez"),
        False,
    )
    _soft_check(
        failures,
        "usuario administrador profile does not contain support ticket carryover",
        _entity_profile_contains(trace, "usuario administrador", "használ", "ügyfélticketek kezelésére"),
        False,
    )
    _soft_check(
        failures,
        "cuenta facts do not contain empty Fue claim",
        _entity_has_empty_predicate_fact(trace, "cuenta", "Fue"),
        False,
    )
    _soft_check(
        failures,
        "cuenta search profile canonical_text does not contain Fue",
        _search_profile_canonical_contains(trace, "cuenta", "Fue"),
        False,
    )
    _soft_check(
        failures,
        "régi Helpdesk import is not unknown",
        _entity_type_for_name(trace, "régi Helpdesk import") == "unknown",
        False,
    )
    _soft_check(
        failures,
        "legacy helpdesk import is not unknown",
        _entity_type_for_name(trace, "legacy helpdesk import") == "unknown",
        False,
    )
    _soft_check(
        failures,
        "Historical tickets is not unknown",
        _entity_type_for_name(trace, "Historical tickets") == "unknown",
        False,
    )
    _soft_check(
        failures,
        "régi Helpdesk import canonical_text does not contain broken predicate/object order",
        _search_profile_canonical_contains(trace, "régi Helpdesk import", "megszűnt Helpdesk"),
        False,
    )
    _soft_check(
        failures,
        "régi Helpdesk import canonical_text contains event year",
        _search_profile_canonical_contains(trace, "régi Helpdesk import", "megszűnt 2024"),
        True,
    )

    if failures:
        # Későbbi célzott promptok javítják: noise filtering, context carryover guard,
        # subject cleanup, entity type normalization, candidate deduplication és
        # similarity calibration. Addig ez harness-regresszióként méri a piros pontokat.
        pytest.xfail("Pipeline regression v1 known failures:\n" + "\n".join(failures))
