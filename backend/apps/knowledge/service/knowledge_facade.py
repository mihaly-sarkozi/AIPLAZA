from __future__ import annotations

import asyncio
from collections.abc import Callable
import logging
import hashlib
import re
import time
import unicodedata
import uuid as uuid_lib
from html import unescape
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Any

from apps.knowledge.domain.context_profile import DEFAULT_CONTEXT_PROFILE, ContextProfile
from apps.knowledge.domain.claim import Claim
from apps.knowledge.domain.corpus import Corpus
from apps.knowledge.domain.document import Document
from apps.knowledge.domain.ingest_event import IngestEvent
from apps.knowledge.domain.ingest_input import IngestInput
from apps.knowledge.domain.ingest_item import IngestItem
from apps.knowledge.domain.ingest_run import IngestRun
from apps.knowledge.domain.local_entity_cluster import LocalEntityCluster
from apps.knowledge.domain.index_build import IndexBuild
from apps.knowledge.domain.index_profile import DEFAULT_INDEX_PROFILE, IndexProfile
from apps.knowledge.domain.interpretation_run import InterpretationRun
from apps.knowledge.domain.mention import Mention
from apps.knowledge.domain.paragraph import Paragraph
from apps.knowledge.domain.parser_run import ParserRun
from apps.knowledge.domain.query_run import Citation, QueryRun
from apps.knowledge.domain.query_profile import query_profile_to_json_dict
from apps.knowledge.domain.retrieval_profile import DEFAULT_RETRIEVAL_PROFILE, RetrievalProfile
from apps.knowledge.domain.sentence import Sentence
from apps.knowledge.domain.sentence_interpretation import SentenceInterpretation
from apps.knowledge.domain.semantic_block import semantic_block_to_json_dict
from apps.knowledge.domain.source import Source
from apps.knowledge.domain.space_time_frame import SpaceTimeFrame
from apps.knowledge.service.claim_split import ClaimFineSplitter
from apps.knowledge.service.claim_extraction_pipeline import run_v1_sentence_claim_pipeline
from apps.knowledge.service.claim_extractor_v1 import ClaimExtractorV1
from apps.knowledge.service.claim_quality_gate import ClaimQualityGate
from apps.knowledge.service.claim_typing import debug_claim_type
from apps.knowledge.service.knowledge_trace_service import KnowledgeTraceService
from apps.knowledge.service.entity_key_normalization import canonicalize_entity_key
from apps.knowledge.service.language_rules import detect_language, fold_text, resolve_language
from apps.knowledge.service.mention_extractor import MentionExtractor, debug_print as debug_print_mentions
from apps.knowledge.service.local_resolver_v1 import LocalResolverV1, attach_local_resolver_metadata
from apps.knowledge.service.space_time_extractor_v1 import SpaceTimeExtractorV1
from apps.knowledge.service.subject_context_resolver_v1 import SubjectContextResolverV1
from apps.knowledge.service.semantic_block_builder_v1 import SemanticBlockBuilderV1
from apps.knowledge.service.technical_entity_builder_v1 import TechnicalEntityBuilderV1
from apps.knowledge.domain.technical_entity import technical_entity_to_json_dict
from apps.knowledge.service.technical_memory_chunk_builder_v1 import TechnicalMemoryChunkBuilderV1
from apps.knowledge.domain.technical_memory_chunk import technical_memory_chunk_to_json_dict
from apps.knowledge.service.search_profile_builder_v1 import SearchProfileBuilderV1
from apps.knowledge.domain.search_profile import SearchProfile, search_profile_to_json_dict
from apps.knowledge.service.candidate_selection_v1 import CandidateSelectionV1, candidate_selection_attempt_count
from apps.knowledge.domain.candidate_selection import entity_candidate_to_json_dict
from apps.knowledge.service.similarity_engine_v1 import SimilarityEngineV1
from apps.knowledge.domain.similarity_analysis import similarity_analysis_to_json_dict
from apps.knowledge.service.decision_engine_v1 import DecisionEngineV1
from apps.knowledge.domain.decision_analysis import decision_analysis_to_json_dict
from apps.knowledge.service.global_profile_builder_v0 import GlobalProfileBuilderV0
from apps.knowledge.service.tension_engine_v1 import TensionEngineV1
from apps.knowledge.domain.tension_analysis import tension_analysis_to_json_dict
from apps.knowledge.service.retrieval_chunk_builder_v0 import RetrievalChunkBuilderV0
from apps.knowledge.service.retrieval_chunk_index_v0 import build_retrieval_chunk_index_rows
from apps.knowledge.service.semantic_block_index_v0 import build_semantic_block_index_rows
from apps.knowledge.service.semantic_block_quality_v0 import enrich_semantic_blocks_with_quality
from apps.knowledge.service.answer_verifier import verify_answer
from apps.knowledge.service.query_resolver_v0 import QueryResolverV0
from apps.knowledge.service.query_aware_retrieval_v0 import QueryAwareRetrievalV0
from apps.knowledge.service.explanation_builder_v0 import ExplanationBuilderV0
from apps.knowledge.service.lineage_builder_v0 import LineageBuilderV0
from apps.knowledge.service.knowledge_quality_report_v0 import KnowledgeQualityReportV0
from apps.knowledge.service.synthesis_engine_v0 import SynthesisEngineV0
from apps.knowledge.service.ports import (
    ClaimStorePort,
    ChunkBuilderPort,
    ContextBuilderPort,
    CorpusStorePort,
    DocumentStorePort,
    IngestEventStorePort,
    IngestInputStorePort,
    IngestItemStorePort,
    IngestRunStorePort,
    IndexBuildStorePort,
    IndexProfileStorePort,
    InterpretationRunStorePort,
    MentionStorePort,
    MetricsStorePort,
    ParagraphStorePort,
    ParserRunStorePort,
    QueryRunStorePort,
    RetrievalEnginePort,
    SpaceTimeFrameStorePort,
    SentenceInterpretationStorePort,
    SentenceStorePort,
    SourceStorePort,
    VectorIndexFactory,
)
from apps.knowledge.training_ingest import build_sentence_rows
from core.capabilities.users.dto import User
from core.platform.auth.auth_dependencies import has_permission
from core.platform.contract.observability import (
    increment_metric as increment_platform_metric,
    log_structured_event,
    observe_metric as observe_platform_metric,
    observability_scope,
)
from core.kernel.config.config_loader import settings
from shared.documents import ExtractedDocument, ExtractedParagraph, extract_document_from_upload, extract_text_from_upload
from shared.object_storage.contracts import ObjectStoragePort
import requests
from sqlalchemy.exc import ProgrammingError

logger = logging.getLogger(__name__)

_RETRIEVAL_TIMEOUT_SECONDS = 3.0
_RETRIEVAL_RETRY_ATTEMPTS = 2
_RETRIEVAL_RETRY_BACKOFF_SECONDS = 0.05


@dataclass(frozen=True)
class SentenceCandidate:
    text: str
    confidence: float
    split_reason: str
    char_start_offset: int
    char_end_offset: int


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _is_uuid_string(value: str | None) -> bool:
    if not value:
        return False
    try:
        uuid_lib.UUID(str(value))
    except ValueError:
        return False
    return True


def _normalize_text_payload(value: str | None) -> str:
    text = str(value or "")
    # Keep user-visible content intact, but normalize technical encoding details.
    text = text.removeprefix("\ufeff")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return unicodedata.normalize("NFC", text)


def _truncate_diagnostic_text(value: str | None, *, limit: int = 220) -> str:
    text = " ".join(str(value or "").strip().split())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)].rstrip() + "..."


def _json_safe(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple | set):
        return [_json_safe(item) for item in value]
    return value


def _empty_claim_quality_summary() -> dict[str, Any]:
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


def _merge_claim_quality_summary(summary: dict[str, Any], diagnostics: dict[str, Any] | None) -> dict[str, Any]:
    if not diagnostics:
        return summary

    merged = {
        **_empty_claim_quality_summary(),
        **dict(summary or {}),
    }
    if diagnostics.get("skipped"):
        merged["skipped_sentence_count"] = int(merged.get("skipped_sentence_count") or 0) + 1
        sentence_reason = str(diagnostics.get("sentence_reason") or "")
        if sentence_reason == "sentence_is_question":
            merged["question_sentence_count"] = int(merged.get("question_sentence_count") or 0) + 1
        elif sentence_reason in {"sentence_is_explicit_noise", "noise_sentence"}:
            merged["noise_sentence_skipped_count"] = (
                int(merged.get("noise_sentence_skipped_count") or 0) + 1
            )
        elif sentence_reason in {"sentence_is_fragment", "sentence_no_meaningful_content"}:
            merged["fragment_sentence_count"] = int(merged.get("fragment_sentence_count") or 0) + 1
        skipped_sentences = list(merged.get("skipped_sentences") or [])
        if len(skipped_sentences) < 10:
            skipped_sentences.append(
                {
                    "sentence_id": diagnostics.get("sentence_id"),
                    "reason": sentence_reason or None,
                    "language": diagnostics.get("language"),
                    "text": _truncate_diagnostic_text(diagnostics.get("sentence_text")),
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
            merged["weak_auxiliary_claim_rejected_count"] = (
                int(merged.get("weak_auxiliary_claim_rejected_count") or 0) + 1
            )
        elif reason == "claim_duplicate_weak":
            merged["duplicate_weak_claim_rejected_count"] = (
                int(merged.get("duplicate_weak_claim_rejected_count") or 0) + 1
            )
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
                    "subject_text": _truncate_diagnostic_text(item.get("subject_text"), limit=80),
                    "predicate": _truncate_diagnostic_text(item.get("predicate"), limit=60),
                    "object_text": _truncate_diagnostic_text(item.get("object_text"), limit=120),
                    "claim_type": item.get("claim_type"),
                    "confidence": item.get("confidence"),
                }
            )
    merged["rejected_claim_examples"] = rejected_examples
    return merged


def _aggregate_ingest_item_quality(items: list[IngestItem]) -> dict[str, Any]:
    summary = _empty_claim_quality_summary()
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


def _uuid_from_trace_value(value: Any) -> uuid_lib.UUID:
    text = str(value or "").strip()
    if text:
        try:
            return uuid_lib.UUID(text)
        except ValueError:
            return uuid_lib.uuid5(uuid_lib.NAMESPACE_URL, text)
    return uuid_lib.uuid4()


def _optional_uuid_from_trace_value(value: Any) -> uuid_lib.UUID | None:
    text = str(value or "").strip()
    if not text:
        return None
    return _uuid_from_trace_value(text)


def _search_profile_from_trace_payload(payload: dict[str, Any]) -> SearchProfile | None:
    if not isinstance(payload, dict):
        return None
    entity_name = str(payload.get("entity_name") or "").strip()
    if not entity_name:
        return None
    return SearchProfile(
        search_profile_id=_uuid_from_trace_value(payload.get("search_profile_id")),
        run_id=_optional_uuid_from_trace_value(payload.get("run_id")),
        source_id=_optional_uuid_from_trace_value(payload.get("source_id")),
        technical_memory_chunk_id=_optional_uuid_from_trace_value(payload.get("technical_memory_chunk_id")),
        technical_entity_id=_optional_uuid_from_trace_value(payload.get("technical_entity_id")),
        local_entity_id=_optional_uuid_from_trace_value(payload.get("local_entity_id")),
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


class KnowledgeFacade:
    _DEMO_PROTECTED_KB_NAMES = {
        "teszt tudástár",
        "test knowledge base",
        "base de conocimiento de prueba",
        "test kb",
    }
    _SENTENCE_ABBREVIATIONS = {
        "dr",
        "mr",
        "mrs",
        "ms",
        "prof",
        "ifj",
        "id",
        "stb",
        "kb",
        "pl",
        "ill",
        "old",
        "u",
        "vs",
        "etc",
        "eg",
        "ie",
        "usa",
    }
    _DATE_MONTH_PATTERN = (
        r"(?:jan(?:\.|uár)?|febr?(?:\.|uár)?|márc(?:\.|ius)?|ápr(?:\.|ilis)?|máj(?:\.|us)?|"
        r"jún(?:\.|ius)?|júl(?:\.|ius)?|aug(?:\.|usztus)?|szept?(?:\.|ember)?|"
        r"okt(?:\.|óber)?|nov(?:\.|ember)?|dec(?:\.|ember)?)"
    )
    _SENTENCE_DATE_PATTERNS = (
        re.compile(r"\b(?:19|20)\d{2}\.\s*(?:1[0-2]|0?[1-9])\.\s*(?:3[01]|[12]\d|0?[1-9])\.?"),
        re.compile(r"\b(?:3[01]|[12]\d|0?[1-9])\.\s*(?:1[0-2]|0?[1-9])\.\s*(?:19|20)\d{2}\.?"),
        re.compile(
            rf"\b(?:19|20)\d{{2}}\.\s*{_DATE_MONTH_PATTERN}\s+(?:0?[1-9]|[12]\d|3[01])\.?",
            flags=re.IGNORECASE,
        ),
        re.compile(
            rf"\b(?:0?[1-9]|[12]\d|3[01])\.\s*{_DATE_MONTH_PATTERN}\s+(?:19|20)\d{{2}}\.?",
            flags=re.IGNORECASE,
        ),
        re.compile(
            rf"\b(?:19|20)\d{{2}}\.\s*{_DATE_MONTH_PATTERN}\s+(?:0?[1-9]|[12]\d|3[01])\.\s+napján\b",
            flags=re.IGNORECASE,
        ),
    )
    _SECTION_MARKER_TOKEN = r"(?:\d+|[A-ZÁÉÍÓÖŐÚÜŰ]|[IVXLCDM]+)"
    _HEADING_MARKER_PATTERN = re.compile(rf"^(({_SECTION_MARKER_TOKEN}\.)+)\s+", flags=re.IGNORECASE)
    _INLINE_HEADING_MARKER_PATTERN = re.compile(rf"(?<!\w)((?:{_SECTION_MARKER_TOKEN}\.){{2,}})\s+", flags=re.IGNORECASE)
    _LIST_MARKER_PAREN_PATTERN = re.compile(r"(?<!\w)([a-záéíóöőúüű]\))\s+", flags=re.IGNORECASE)
    _NUMERIC_LIST_BOUNDARY_PATTERN = re.compile(r"\s+\d{1,2}\.\s+[A-ZÁÉÍÓÖŐÚÜŰ]")
    _SOFT_SENTENCE_STARTERS = {
        "A",
        "Az",
        "Ez",
        "Egy",
        "De",
        "És",
        "Viszont",
        "Majd",
        "Akkor",
        "Utána",
        "Továbbá",
        "Közben",
        "Ha",
        "Mert",
        "Amikor",
        "Van",
        "Itt",
        "This",
        "That",
        "Then",
        "However",
        "But",
        "And",
        "Next",
    }
    _PARSER_ERROR_MESSAGE_MAX = 1000
    _INTERPRETATION_ERROR_MESSAGE_MAX = 480
    _CLAIM_STRONG_CONFIDENCE = 0.6
    _STALE_PARSER_RESTART_AFTER_SEC = 30
    _ENABLE_CLAIM_FINE_SPLIT_DURING_PARSING = True
    _CLAIM_FINE_SPLIT_ALLOWED_BLOCK_TYPES = {"paragraph", "list_item"}
    _CLAIM_FINE_SPLIT_MIN_WORDS = 12
    _CLAIM_FINE_SPLIT_MIN_SIGNAL_SCORE = 2
    _CLAIM_FINE_SPLIT_MAX_BLOCKS_PER_DOCUMENT = 80
    _CLAIM_FINE_SPLIT_MAX_BLOCK_RATIO = 0.15
    _CLAIM_FINE_SPLIT_EARLY_STOP_AFTER_BLOCKS = 24
    _CLAIM_FINE_SPLIT_MIN_HIT_BLOCKS_TO_CONTINUE = 2
    _CLAIM_FINE_SPLIT_CONNECTOR_PATTERN = re.compile(
        r"\b(?:és|vagy|illetve|valamint|továbbá|azonban|viszont|ha|amennyiben|kivéve|feltéve)\b",
        flags=re.IGNORECASE,
    )
    _CLAIM_FINE_SPLIT_PREDICATE_PATTERN = re.compile(
        r"\b(?:kell|köteles|jogosult|lehet|van|minősül|alkalmazandó|teljesít(?:hető)?|fizet|"
        r"biztosít|nyújt|történ(?:ik|jen)|áll|érvényes|megszűnik|létrejön|köt|értesít|küld|visel)\b",
        flags=re.IGNORECASE,
    )

    def __init__(
        self,
        *,
        corpus_store: CorpusStorePort,
        user_repo: Any = None,
        source_store: SourceStorePort,
        ingest_run_store: IngestRunStorePort,
        ingest_item_store: IngestItemStorePort,
        ingest_input_store: IngestInputStorePort,
        ingest_event_store: IngestEventStorePort,
        parser_run_store: ParserRunStorePort,
        document_store: DocumentStorePort,
        paragraph_store: ParagraphStorePort,
        sentence_store: SentenceStorePort,
        interpretation_run_store: InterpretationRunStorePort | None = None,
        sentence_interpretation_store: SentenceInterpretationStorePort | None = None,
        mention_store: MentionStorePort | None = None,
        claim_store: ClaimStorePort | None = None,
        space_time_frame_store: SpaceTimeFrameStorePort | None = None,
        local_entity_cluster_repository: Any | None = None,
        claim_fine_splitter: ClaimFineSplitter | None = None,
        index_profile_store: IndexProfileStorePort,
        index_build_store: IndexBuildStorePort,
        query_run_store: QueryRunStorePort,
        chunk_builder: ChunkBuilderPort,
        retrieval_engine: RetrievalEnginePort,
        context_builder: ContextBuilderPort,
        vector_index_factory: VectorIndexFactory,
        metrics_store: MetricsStorePort,
        object_storage: ObjectStoragePort,
    ) -> None:
        self._corpus_store = corpus_store
        self._user_repo = user_repo
        self._source_store = source_store
        self._ingest_run_store = ingest_run_store
        self._ingest_item_store = ingest_item_store
        self._ingest_input_store = ingest_input_store
        self._ingest_event_store = ingest_event_store
        self._parser_run_store = parser_run_store
        self._document_store = document_store
        self._paragraph_store = paragraph_store
        self._sentence_store = sentence_store
        self._interpretation_run_store = interpretation_run_store
        self._sentence_interpretation_store = sentence_interpretation_store
        self._mention_store = mention_store
        self._claim_store = claim_store
        self._space_time_frame_store = space_time_frame_store
        self._local_entity_cluster_repository = local_entity_cluster_repository
        self._claim_fine_splitter = claim_fine_splitter
        self._mention_extractor = MentionExtractor()
        self._claim_quality_gate = ClaimQualityGate()
        self._claim_extractor_v1 = ClaimExtractorV1(quality_gate=self._claim_quality_gate)
        self._space_time_extractor_v1 = SpaceTimeExtractorV1()
        self._local_resolver_v1 = LocalResolverV1()
        self._trace_service = KnowledgeTraceService(
            ingest_run_store=self._ingest_run_store,
            ingest_item_store=self._ingest_item_store,
            source_store=self._source_store,
            document_store=self._document_store,
            sentence_store=self._sentence_store,
            mention_store=self._mention_store,
            claim_store=self._claim_store,
            space_time_frame_store=self._space_time_frame_store,
            interpretation_run_store=self._interpretation_run_store,
            local_entity_cluster_repository=self._local_entity_cluster_repository,
        )
        self._index_profile_store = index_profile_store
        self._index_build_store = index_build_store
        self._query_run_store = query_run_store
        self._chunk_builder = chunk_builder
        self._retrieval_engine = retrieval_engine
        self._context_builder = context_builder
        self._vector_index_factory = vector_index_factory
        self._metrics_store = metrics_store
        self._object_storage = object_storage
        self._feedback_events: list[dict[str, Any]] = []
        self._source_withdrawal_events: list[dict[str, Any]] = []

    def _log_step(self, step: str, *, status: str, tenant: str | None = None, duration_ms: float | None = None, **counts: object) -> None:
        payload = {
            "step": step,
            "status": status,
            "tenant": tenant,
            "duration_ms": round(duration_ms, 2) if duration_ms is not None else None,
        }
        payload.update(counts)
        logger.info("knowledge.pipeline", extra={"knowledge": payload})

    @staticmethod
    def _delete_for_corpus_if_table_exists(store: Any, corpus_uuid: str, *, table_name: str) -> int:
        try:
            return int(store.delete_for_corpus(corpus_uuid))
        except ProgrammingError as exc:
            message = str(exc).lower()
            if "does not exist" in message and table_name.lower() in message:
                logger.warning(
                    "knowledge.clear_contents.skip_missing_table",
                    extra={"corpus_uuid": corpus_uuid, "table_name": table_name},
                )
                return 0
            raise

    @staticmethod
    def _delete_for_document_if_table_exists(store: Any, document_id: str, *, table_name: str) -> int:
        try:
            return int(store.delete_for_document(document_id))
        except ProgrammingError as exc:
            message = str(exc).lower()
            if "does not exist" in message and table_name.lower() in message:
                logger.warning(
                    "knowledge.reprocess.skip_missing_table",
                    extra={"document_id": document_id, "table_name": table_name},
                )
                return 0
            raise

    @staticmethod
    def _is_missing_table_error(exc: Exception, *table_names: str) -> bool:
        message = str(exc).lower()
        return "does not exist" in message and any(table_name.lower() in message for table_name in table_names)

    @staticmethod
    def _truncate_error_message(value: Any, *, max_length: int) -> str:
        text = str(value or "").strip()
        if len(text) <= max_length:
            return text
        suffix = "... [truncated]"
        keep = max(0, max_length - len(suffix))
        return f"{text[:keep]}{suffix}"

    def _load_existing_search_profiles(
        self,
        *,
        corpus_uuid: str,
        exclude_interpretation_run_id: str | None,
        limit: int = 20,
    ) -> list[SearchProfile]:
        if self._interpretation_run_store is None:
            return []
        list_for_corpus = getattr(self._interpretation_run_store, "list_for_corpus", None)
        if not callable(list_for_corpus):
            return []
        try:
            runs = list_for_corpus(corpus_uuid, limit=limit)
        except ProgrammingError as exc:
            if self._is_missing_table_error(exc, "knowledge_interpretation_runs"):
                return []
            raise
        profiles: list[SearchProfile] = []
        for previous_run in runs:
            if str(previous_run.id) == str(exclude_interpretation_run_id or ""):
                continue
            if previous_run.status != "completed":
                continue
            metadata = dict(previous_run.metadata or {})
            for item in metadata.get("search_profiles") or []:
                profile = _search_profile_from_trace_payload(item) if isinstance(item, dict) else None
                if profile is not None:
                    profiles.append(profile)
        return profiles

    def _load_existing_global_profiles(
        self,
        *,
        corpus_uuid: str,
        exclude_interpretation_run_id: str | None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        if self._interpretation_run_store is None:
            return []
        list_for_corpus = getattr(self._interpretation_run_store, "list_for_corpus", None)
        if not callable(list_for_corpus):
            return []
        try:
            runs = list_for_corpus(corpus_uuid, limit=limit)
        except ProgrammingError as exc:
            if self._is_missing_table_error(exc, "knowledge_interpretation_runs"):
                return []
            raise
        profiles_by_id: dict[str, dict[str, Any]] = {}
        for previous_run in reversed(runs):
            if str(previous_run.id) == str(exclude_interpretation_run_id or ""):
                continue
            if previous_run.status != "completed":
                continue
            metadata = dict(previous_run.metadata or {})
            for item in metadata.get("global_profiles") or []:
                if not isinstance(item, dict):
                    continue
                profile_id = str(item.get("profile_id") or "")
                if not profile_id:
                    continue
                profiles_by_id[profile_id] = dict(item)
        return list(profiles_by_id.values())

    def _load_existing_retrieval_chunks(
        self,
        *,
        corpus_uuid: str,
        exclude_interpretation_run_id: str | None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        if self._interpretation_run_store is None:
            return []
        list_for_corpus = getattr(self._interpretation_run_store, "list_for_corpus", None)
        if not callable(list_for_corpus):
            return []
        try:
            runs = list_for_corpus(corpus_uuid, limit=limit)
        except ProgrammingError as exc:
            if self._is_missing_table_error(exc, "knowledge_interpretation_runs"):
                return []
            raise
        chunks_by_profile_id: dict[str, dict[str, Any]] = {}
        for previous_run in reversed(runs):
            if str(previous_run.id) == str(exclude_interpretation_run_id or ""):
                continue
            if previous_run.status != "completed":
                continue
            metadata = dict(previous_run.metadata or {})
            for item in metadata.get("retrieval_chunks") or []:
                if not isinstance(item, dict):
                    continue
                profile_id = str(item.get("profile_id") or "")
                if not profile_id:
                    continue
                chunks_by_profile_id[profile_id] = dict(item)
        return list(chunks_by_profile_id.values())

    def _load_existing_semantic_blocks(
        self,
        *,
        corpus_uuid: str,
        exclude_interpretation_run_id: str | None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        if self._interpretation_run_store is None:
            return []
        list_for_corpus = getattr(self._interpretation_run_store, "list_for_corpus", None)
        if not callable(list_for_corpus):
            return []
        try:
            runs = list_for_corpus(corpus_uuid, limit=limit)
        except ProgrammingError as exc:
            if self._is_missing_table_error(exc, "knowledge_interpretation_runs"):
                return []
            raise
        blocks_by_id: dict[str, dict[str, Any]] = {}
        for previous_run in reversed(runs):
            if str(previous_run.id) == str(exclude_interpretation_run_id or ""):
                continue
            if previous_run.status != "completed":
                continue
            metadata = dict(previous_run.metadata or {})
            for item in metadata.get("semantic_blocks") or []:
                if not isinstance(item, dict):
                    continue
                block_id = str(item.get("id") or "")
                if not block_id:
                    continue
                blocks_by_id[block_id] = dict(item)
        return list(blocks_by_id.values())

    @staticmethod
    def _semantic_block_search_text(block: dict[str, Any]) -> str:
        parts = [
            block.get("summary"),
            block.get("primary_subject"),
            block.get("primary_space"),
            block.get("primary_time"),
            block.get("text"),
            " ".join(str(item or "") for item in block.get("predicates") or []),
            " ".join(str(item or "") for item in block.get("space_values") or []),
            " ".join(str(item or "") for item in block.get("time_values") or []),
        ]
        return fold_text(" ".join(str(part or "") for part in parts))

    @staticmethod
    def _query_terms_for_blocks(query_profile: dict[str, Any] | None, query: str | None) -> set[str]:
        values: list[str] = [str(query or "")]
        profile = dict(query_profile or {})
        for key in ("query", "subject", "object", "expected_answer_type", "temporal_scope", "intent"):
            values.append(str(profile.get(key) or ""))
        for key in ("detected_entities", "keywords", "entity_keys", "space_values", "time_values"):
            raw = profile.get(key)
            if isinstance(raw, list):
                values.extend(str(item or "") for item in raw)
        terms: set[str] = set()
        stopwords = {"hogy", "mert", "amikor", "mikor", "mit", "milyen", "csinal", "csinál", "az", "egy", "the", "and"}
        for value in values:
            for token in fold_text(str(value or "")).replace("_", " ").split():
                token = token.strip(".,:;!?()[]{}\"'")
                if len(token) >= 2 and token not in stopwords:
                    terms.add(token)
        return terms

    @staticmethod
    def _query_phrase_for_blocks(query: str | None) -> str:
        stopwords = {"a", "az", "egy", "mit", "miket", "milyen", "hogyan", "hogy", "csinal", "csinál", "rendszer?"}
        tokens: list[str] = []
        for token in fold_text(str(query or "")).replace("_", " ").split():
            cleaned = token.strip(".,:;!?()[]{}\"'")
            if cleaned and cleaned not in stopwords:
                tokens.append(cleaned)
        return " ".join(tokens)

    @staticmethod
    def _is_broad_function_query(query: str | None, query_profile: dict[str, Any] | None) -> bool:
        text = fold_text(str(query or ""))
        profile = dict(query_profile or {})
        expected = fold_text(str(profile.get("expected_answer_type") or ""))
        return "mit csinal" in text or "mire valo" in text or expected in {"object", "summary"}

    @staticmethod
    def _select_semantic_blocks_for_query(
        *,
        semantic_blocks: list[dict[str, Any]],
        matched_claims: list[dict[str, Any]],
        matched_chunks: list[dict[str, Any]],
        query_profile: dict[str, Any] | None = None,
        query: str | None = None,
        max_blocks: int = 4,
    ) -> list[dict[str, Any]]:
        claim_ids = {
            str(claim.get("claim_id") or "").strip()
            for claim in matched_claims
            if str(claim.get("claim_id") or "").strip()
        }
        profile_source_ids = {
            str(source_id or "").strip()
            for chunk in matched_chunks
            for source_id in (chunk.get("source_ids") or [])
            if str(source_id or "").strip()
        }
        query_terms = KnowledgeFacade._query_terms_for_blocks(query_profile, query)
        query_phrase = KnowledgeFacade._query_phrase_for_blocks(query)
        broad_function_query = KnowledgeFacade._is_broad_function_query(query, query_profile)
        scored: list[tuple[float, dict[str, Any]]] = []
        for block in semantic_blocks:
            block_status = str(block.get("block_status") or (block.get("metadata") or {}).get("block_status") or "draft").lower()
            if block_status in {"rejected", "withdrawn"}:
                continue
            score = 0.0
            block_claim_ids = {str(item or "").strip() for item in block.get("claim_ids") or [] if str(item or "").strip()}
            if claim_ids and block_claim_ids.intersection(claim_ids):
                score += 3.0
            source_id = str(block.get("source_id") or "").strip()
            if source_id and source_id in profile_source_ids:
                score += 0.25
            search_text = KnowledgeFacade._semantic_block_search_text(block)
            sentence_count = int((block.get("metadata") or {}).get("sentence_count") or len(block.get("sentence_ids") or []) or 0)
            exact_phrase_match = bool(query_phrase and len(query_phrase) >= 4 and query_phrase in search_text)
            if exact_phrase_match:
                score += 4.0
            if query_terms:
                matched_terms = {term for term in query_terms if term in search_text}
                coverage = len(matched_terms) / max(1, len(query_terms))
                score += min(4.0, len(matched_terms) * 0.8)
                if coverage >= 0.75:
                    score += 1.0
            else:
                matched_terms = set()
            if broad_function_query and exact_phrase_match and sentence_count >= 3:
                score += 4.0
            elif broad_function_query and sentence_count >= 3 and query_terms and len(matched_terms) >= 2:
                score += 2.0
            if broad_function_query and sentence_count <= 1 and not exact_phrase_match:
                score -= 0.5
            if score > 0:
                retrieval_weight = float(block.get("retrieval_weight") or (block.get("metadata") or {}).get("retrieval_weight") or 1.0)
                quality_adjusted_score = score * max(0.0, retrieval_weight)
                enriched = dict(block)
                enriched["match_score"] = round(quality_adjusted_score, 4)
                enriched["match_reason"] = {
                    "claim_overlap": bool(claim_ids and block_claim_ids.intersection(claim_ids)),
                    "source_overlap": bool(source_id and source_id in profile_source_ids),
                    "exact_query_phrase": exact_phrase_match,
                    "broad_function_query": broad_function_query,
                    "sentence_count": sentence_count,
                    "query_terms": sorted(matched_terms)[:12],
                    "base_score": round(score, 4),
                    "retrieval_weight": round(retrieval_weight, 4),
                    "block_status": block_status,
                    "source_reliability": block.get("source_reliability") or (block.get("metadata") or {}).get("source_reliability"),
                    "conflict_count": block.get("conflict_count") or (block.get("metadata") or {}).get("conflict_count") or 0,
                }
                scored.append((quality_adjusted_score, enriched))
        deduped: list[dict[str, Any]] = []
        seen: set[str] = set()
        for _score, block in sorted(scored, key=lambda item: (-item[0], int(item[1].get("order_start") or 0))):
            block_id = str(block.get("id") or "")
            if block_id in seen:
                continue
            seen.add(block_id)
            deduped.append(block)
            if len(deduped) >= max_blocks:
                break
        return deduped

    @staticmethod
    def _semantic_blocks_context(blocks: list[dict[str, Any]], *, max_chars: int = 6000) -> str:
        parts: list[str] = []
        total = 0
        for index, block in enumerate(blocks, start=1):
            text = str(block.get("text") or "").strip()
            if not text:
                continue
            heading = str(block.get("summary") or block.get("primary_subject") or f"Semantic block {index}").strip()
            subject = str(block.get("primary_subject") or "-").strip() or "-"
            space = str(block.get("primary_space") or ", ".join(block.get("space_values") or []) or "-").strip() or "-"
            time = str(block.get("primary_time") or ", ".join(block.get("time_values") or []) or "-").strip() or "-"
            source_id = str(block.get("source_id") or "-").strip() or "-"
            block_id = str(block.get("id") or "-").strip() or "-"
            part = (
                f"[Tudásblokk {index}: {heading}]\n"
                f"block_id={block_id}; source_id={source_id}; alany={subject}; hely={space}; idő={time}\n"
                f"{text}"
            )
            if total + len(part) > max_chars:
                break
            parts.append(part)
            total += len(part)
        return "\n\n".join(parts)

    @staticmethod
    def _retrieval_chunks_from_vector_hits(hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
        chunks: list[dict[str, Any]] = []
        for hit in hits:
            payload = dict(hit.get("payload") or {})
            if payload.get("point_type") != "retrieval_chunk":
                continue
            metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
            profile_id = str(payload.get("profile_id") or metadata.get("profile_id") or "").strip()
            if not profile_id:
                continue
            chunks.append(
                {
                    "retrieval_chunk_id": metadata.get("retrieval_chunk_id") or f"retrieval_chunk:{profile_id}",
                    "profile_id": profile_id,
                    "entity_name": payload.get("entity_name"),
                    "entity_type": payload.get("entity_type"),
                    "canonical_key": payload.get("canonical_key") or metadata.get("canonical_key"),
                    "retrieval_chunk_text": payload.get("text") or metadata.get("retrieval_chunk_text"),
                    "structured_facts": metadata.get("structured_facts") or {},
                    "evidence_ids": list(metadata.get("evidence_ids") or []),
                    "source_ids": list(metadata.get("source_ids") or []),
                    "conflicting": bool(metadata.get("conflicting")),
                    "temporal_context_included": bool(metadata.get("temporal_context_included")),
                    "vector_score": hit.get("fusion_score") or hit.get("score"),
                }
            )
        return chunks

    @staticmethod
    def _semantic_blocks_from_vector_hits(hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
        blocks: list[dict[str, Any]] = []
        seen: set[str] = set()
        for hit in hits:
            payload = dict(hit.get("payload") or {})
            if payload.get("point_type") != "semantic_block":
                continue
            metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
            block_id = str(payload.get("block_id") or metadata.get("block_id") or "").strip()
            if not block_id or block_id in seen:
                continue
            seen.add(block_id)
            block = {
                "id": block_id,
                "corpus_uuid": metadata.get("corpus_uuid"),
                "source_id": payload.get("source_id") or metadata.get("source_id"),
                "document_id": payload.get("document_id") or metadata.get("document_id"),
                "paragraph_ids": list(metadata.get("paragraph_ids") or []),
                "sentence_ids": list(payload.get("sentence_ids") or metadata.get("sentence_ids") or []),
                "claim_ids": list(payload.get("claim_ids") or metadata.get("claim_ids") or []),
                "order_start": metadata.get("order_start") or 0,
                "order_end": metadata.get("order_end") or 0,
                "primary_subject": payload.get("subject") or metadata.get("primary_subject") or "",
                "subject_key": payload.get("subject_key") or metadata.get("subject_key") or "",
                "primary_space": payload.get("space") or metadata.get("primary_space") or "",
                "space_key": payload.get("space_key") or metadata.get("space_key") or "",
                "primary_time": payload.get("time") or metadata.get("primary_time") or "",
                "time_key": payload.get("time_key") or metadata.get("time_key") or "",
                "block_type": metadata.get("block_type") or "semantic_unit",
                "text": metadata.get("text") or payload.get("raw_block_text") or payload.get("text") or "",
                "summary": metadata.get("summary") or "",
                "predicates": list(metadata.get("predicates") or []),
                "entity_keys": list(payload.get("entity_keys") or metadata.get("entity_keys") or []),
                "space_modes": list(payload.get("space_modes") or metadata.get("space_modes") or []),
                "space_values": list(metadata.get("space_values") or []),
                "time_modes": list(payload.get("time_modes") or metadata.get("time_modes") or []),
                "time_values": list(metadata.get("time_values") or []),
                "confidence": metadata.get("confidence") or 0.0,
                "block_status": payload.get("block_status") or metadata.get("block_status") or "draft",
                "source_reliability": payload.get("source_reliability") or metadata.get("source_reliability") or 0.0,
                "retrieval_weight": payload.get("retrieval_weight") or metadata.get("retrieval_weight") or 1.0,
                "conflict_count": payload.get("conflict_count") or metadata.get("conflict_count") or 0,
                "conflicts": list(metadata.get("conflicts") or []),
                "builder_version": metadata.get("builder_version") or "",
                "metadata": dict(metadata.get("metadata") or {}),
                "match_score": round(float(hit.get("fusion_score") or hit.get("score") or 0.0), 4),
                "match_reason": {
                    "vector_hit": True,
                    "semantic_score": hit.get("semantic_score"),
                    "lexical_score": hit.get("lexical_score"),
                    "fusion_score": hit.get("fusion_score"),
                    "quality_score": payload.get("quality_score_explanation") or {},
                    "point_type": "semantic_block",
                },
            }
            blocks.append(block)
        return blocks

    @staticmethod
    def _order_chunks_by_vector_hits(retrieval_chunks: list[dict[str, Any]], hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
        vector_profile_ids = [
            str((hit.get("payload") or {}).get("profile_id") or "").strip()
            for hit in hits
            if (hit.get("payload") or {}).get("point_type") == "retrieval_chunk"
        ]
        vector_profile_ids = [item for item in vector_profile_ids if item]
        if not vector_profile_ids:
            return retrieval_chunks
        rank = {profile_id: index for index, profile_id in enumerate(vector_profile_ids)}
        matched = [chunk for chunk in retrieval_chunks if str(chunk.get("profile_id") or "") in rank]
        if not matched:
            return KnowledgeFacade._retrieval_chunks_from_vector_hits(hits) or retrieval_chunks
        remainder = [chunk for chunk in retrieval_chunks if str(chunk.get("profile_id") or "") not in rank]
        return sorted(matched, key=lambda chunk: rank.get(str(chunk.get("profile_id") or ""), 9999)) + remainder

    @staticmethod
    def _compute_progress_percent(processed_parts: int | None, total_parts: int | None) -> int | None:
        if processed_parts is None or total_parts is None or total_parts <= 0:
            return None
        return max(0, min(100, int(round((processed_parts / total_parts) * 100))))

    @classmethod
    def _build_processing_module(
        cls,
        *,
        key: str,
        status: str,
        label: str,
        processed_parts: int | None = None,
        total_parts: int | None = None,
        run_id: str | None = None,
        message: str | None = None,
        error_message: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "key": key,
            "status": status,
            "label": label,
            "processed_parts": processed_parts,
            "total_parts": total_parts,
            "progress_percent": cls._compute_progress_percent(processed_parts, total_parts),
        }
        if run_id:
            payload["run_id"] = run_id
        if message:
            payload["message"] = message
        if error_message:
            payload["error_message"] = error_message
        return payload

    @classmethod
    def _build_document_progress(
        cls,
        *,
        phase: str,
        processed_parts: int | None,
        total_parts: int | None,
        label: str,
    ) -> dict[str, Any]:
        return {
            "phase": phase,
            "processed_parts": processed_parts,
            "total_parts": total_parts,
            "progress_percent": cls._compute_progress_percent(processed_parts, total_parts),
            "label": label,
        }

    @classmethod
    def _compute_item_progress_percent(cls, item: IngestItem) -> int | None:
        summary = dict((item.metadata or {}).get("processing_summary") or {})
        document_progress = summary.get("document_progress")
        modules = summary.get("modules")
        if item.status in {"completed", "duplicate", "rejected"}:
            return 100
        if item.status == "failed":
            return 100
        parser_status = None
        interpretation_status = None
        evaluation_status = None
        interpretation_progress = None
        if isinstance(modules, dict):
            parser = modules.get("parser")
            interpretation = modules.get("sentence_interpretation")
            evaluation = modules.get("sentence_evaluation")
            if isinstance(parser, dict):
                parser_status = str(parser.get("status") or "") or None
            if isinstance(interpretation, dict):
                interpretation_status = str(interpretation.get("status") or "") or None
                progress_percent = interpretation.get("progress_percent")
                if isinstance(progress_percent, (int, float)):
                    interpretation_progress = max(0, min(100, int(round(progress_percent))))
            if isinstance(evaluation, dict):
                evaluation_status = str(evaluation.get("status") or "") or None
        if interpretation_status == "completed" and evaluation_status in {"completed", "skipped", None}:
            return 100
        if interpretation_status == "processing":
            base = 55
            scaled = int(round((interpretation_progress or 0) * 0.45))
            return max(base, min(99, base + scaled))
        if interpretation_status == "queued" and parser_status == "completed":
            return 55
        if parser_status == "completed":
            return 55
        if parser_status == "processing":
            if isinstance(document_progress, dict):
                phase = str(document_progress.get("phase") or "")
                if phase == "parser":
                    progress_percent = document_progress.get("progress_percent")
                    if isinstance(progress_percent, (int, float)) and progress_percent > 0:
                        return max(20, min(50, int(round(progress_percent * 0.5))))
            return 30
        if item.status == "processing":
            progress_message = str(item.progress_message or "").lower()
            if "validáció" in progress_message or "előkészítés" in progress_message:
                return 10
            if "parser" in progress_message:
                return 30
            return 15
        if item.status in {"validated", "queued"}:
            return 5
        return 0

    @classmethod
    def _build_run_progress_summary(cls, run: IngestRun, items: list[IngestItem]) -> dict[str, Any]:
        total_items = max(len(items), 1)
        terminal_items = sum(1 for item in items if item.status in {"completed", "failed", "duplicate", "rejected"})
        item_progress_total = sum(cls._compute_item_progress_percent(item) or 0 for item in items)
        overall_percent = max(0, min(100, int(round(item_progress_total / total_items)))) if items else 0

        active_item = next((item for item in items if item.status == "processing"), None)
        queued_item = next((item for item in items if item.status in {"received", "validated", "queued"}), None)
        focus_item = active_item or queued_item or (items[-1] if items else None)
        focus_summary = (
            dict((focus_item.metadata or {}).get("processing_summary") or {})
            if focus_item is not None
            else {}
        )
        focus_document_progress = focus_summary.get("document_progress") if isinstance(focus_summary, dict) else None
        focus_modules = focus_summary.get("modules") if isinstance(focus_summary, dict) else None
        active_module = None
        active_module_label = None
        active_module_message = None
        if isinstance(focus_document_progress, dict):
            active_module = focus_document_progress.get("phase")
            active_module_message = focus_document_progress.get("label")
        if isinstance(focus_modules, dict):
            for module in focus_modules.values():
                if isinstance(module, dict) and module.get("status") == "processing":
                    active_module = str(module.get("key") or active_module or "")
                    active_module_label = str(module.get("label") or "") or None
                    active_module_message = str(module.get("message") or active_module_message or "") or None
                    break

        last_error_message = None
        stopped_at = None
        failed_item = next((item for item in reversed(items) if item.status == "failed"), None)
        if failed_item is not None:
            failed_summary = dict((failed_item.metadata or {}).get("processing_summary") or {})
            failed_modules = failed_summary.get("modules")
            if isinstance(failed_modules, dict):
                for module in failed_modules.values():
                    if isinstance(module, dict) and module.get("status") == "failed":
                        stopped_at = str(module.get("key") or "") or None
                        active_module_label = str(module.get("label") or "") or active_module_label
                        last_error_message = str(module.get("error_message") or "") or None
                        break
            if stopped_at is None:
                document_progress = failed_summary.get("document_progress")
                if isinstance(document_progress, dict):
                    stopped_at = str(document_progress.get("phase") or "") or None
            if not last_error_message:
                last_error_message = str(failed_item.error_message or "").strip() or None

        return {
            "total_items": len(items),
            "terminal_items": terminal_items,
            "overall_percent": 100 if run.status == "completed" else overall_percent,
            "active_item_id": focus_item.id if focus_item is not None else None,
            "active_item_label": focus_item.display_name if focus_item is not None else None,
            "active_item_status": focus_item.status if focus_item is not None else None,
            "active_module": active_module,
            "active_module_label": active_module_label,
            "active_message": active_module_message or (focus_item.progress_message if focus_item is not None else None),
            "stopped_at": stopped_at,
            "last_error_message": last_error_message,
        }

    def _update_item_processing_summary(
        self,
        item: IngestItem,
        *,
        progress_message: str | None = None,
        module_updates: dict[str, dict[str, Any]] | None = None,
        document_progress: dict[str, Any] | None = None,
        extra_metadata: dict[str, Any] | None = None,
    ) -> IngestItem:
        metadata = dict(item.metadata or {})
        summary = dict(metadata.get("processing_summary") or {})
        modules = dict(summary.get("modules") or {})
        if module_updates:
            modules.update(module_updates)
        summary["modules"] = modules
        if document_progress is not None:
            summary["document_progress"] = document_progress
        if modules:
            if any(module.get("status") == "failed" for module in modules.values()):
                summary["overall_status"] = "failed"
            elif all(module.get("status") == "completed" for module in modules.values()):
                summary["overall_status"] = "completed"
            elif any(module.get("status") == "processing" for module in modules.values()):
                summary["overall_status"] = "processing"
            elif any(module.get("status") == "skipped" for module in modules.values()):
                summary["overall_status"] = "partial"
            else:
                summary["overall_status"] = "queued"
        metadata["processing_summary"] = summary
        if extra_metadata:
            metadata.update(extra_metadata)
        return self._ingest_item_store.update(
            replace(
                item,
                progress_message=progress_message if progress_message is not None else item.progress_message,
                updated_at=_utcnow(),
                metadata=metadata,
            )
        )

    @staticmethod
    def _to_corpus(item: Any, *, tenant: str = "") -> Corpus:
        return Corpus(
            id=getattr(item, "id", None),
            tenant=tenant,
            uuid=str(getattr(item, "uuid")),
            name=str(getattr(item, "name")),
            description=getattr(item, "description", None),
            qdrant_collection_name=str(getattr(item, "qdrant_collection_name")),
            created_at=getattr(item, "created_at", None),
            updated_at=getattr(item, "updated_at", None),
            personal_data_mode=str(getattr(item, "personal_data_mode", "no_personal_data")),
            personal_data_sensitivity=str(getattr(item, "personal_data_sensitivity", "medium")),
        )

    def _user_repo_list_all(self) -> list[Any]:
        if self._user_repo is None or not hasattr(self._user_repo, "list_all"):
            return []
        return self._user_repo.list_all()

    def _default_index_profile(self, key: str | None = None) -> IndexProfile:
        if key:
            profile = self._index_profile_store.get(key)
            if profile is not None:
                return profile
        return DEFAULT_INDEX_PROFILE

    @staticmethod
    def _sha256_bytes(content: bytes) -> str:
        return hashlib.sha256(content).hexdigest()

    @staticmethod
    def _sha256_text(content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def _record_ingest_event(
        self,
        *,
        run_id: str,
        event_type: str,
        status: str,
        item_id: str | None = None,
        message: str | None = None,
        created_by: int | None = None,
        **details: Any,
    ) -> IngestEvent:
        event = IngestEvent(
            ingest_run_id=run_id,
            ingest_item_id=item_id,
            event_type=event_type,
            status=status,
            message=message,
            created_by=created_by,
            details=details,
        )
        created = self._ingest_event_store.create(event)
        log_structured_event(
            "apps.knowledge.ingest",
            event_type,
            level=logging.INFO if status not in {"failed", "error"} else logging.ERROR,
            event_type=event_type,
            status=status,
            ingest_run_id=run_id,
            ingest_item_id=item_id,
            details=details,
            message=message,
        )
        return created

    @staticmethod
    def _normalize_parser_text(value: str | None) -> str:
        text = _normalize_text_payload(value)
        text = re.sub(r"(?<=\S)-\s*\n\s*(?=[A-Za-zÁÉÍÓÖŐÚÜŰáéíóöőúüű0-9])", "", text)
        lines = [line.rstrip() for line in text.split("\n")]
        return "\n".join(lines).strip()

    @staticmethod
    def _describe_empty_extraction(metadata: dict[str, Any] | None) -> str:
        info = dict(metadata or {})
        if info.get("source_format") == "pdf" and info.get("no_extractable_text"):
            page_count = int(info.get("page_count") or 0)
            producer = str(info.get("pdf_producer") or "").strip()
            creator = str(info.get("pdf_creator") or "").strip()
            title = str(info.get("pdf_title") or "").strip()
            details: list[str] = []
            if page_count > 0:
                details.append(f"{page_count} oldalas PDF")
            if producer:
                details.append(f"producer: {producer}")
            if creator:
                details.append(f"creator: {creator}")
            if title:
                details.append(f"cím: {title}")
            detail_text = f" ({'; '.join(details)})" if details else ""
            return (
                "A PDF-ből nem nyerhető ki szöveg, mert nem tartalmaz kiolvasható szövegréteget"
                f"{detail_text}. Valószínűleg képalapú vagy szkennelt PDF, ezért OCR szükséges."
            )
        return "A forrásból nem nyerhető ki feldolgozható szöveg."

    @staticmethod
    def _split_paragraphs(text: str) -> list[str]:
        if not text.strip():
            return []
        chunks = [chunk.strip() for chunk in text.split("\n\n")]
        return [chunk for chunk in chunks if chunk]

    @staticmethod
    def _normalize_sentence_candidate_text(value: str) -> str:
        return re.sub(r"\s+", " ", str(value or "")).strip()

    @staticmethod
    def _sentence_word_count(value: str) -> int:
        return len(re.findall(r"\b\w+\b", value, flags=re.UNICODE))

    @staticmethod
    def _looks_like_noise_sentence_candidate(text: str) -> bool:
        normalized = KnowledgeFacade._normalize_sentence_candidate_text(text)
        if not normalized:
            return True
        words = re.findall(r"\b\w+\b", normalized, flags=re.UNICODE)
        if len(words) < 3:
            return True
        if re.fullmatch(r"[\d\s.,;:!?()\"'\-_/\\]+", normalized):
            return True
        if re.fullmatch(r"[\W_]+", normalized, flags=re.UNICODE):
            return True
        return False

    @staticmethod
    def _next_token(text: str, start_idx: int) -> str:
        match = re.search(r"[\"'„“”‘’(\[]*([A-Za-zÁÉÍÓÖŐÚÜŰáéíóöőúüű0-9]+)", text[start_idx:])
        return match.group(1) if match else ""

    @staticmethod
    def _token_with_period_before(text: str, end_idx: int) -> str:
        prefix = text[: end_idx + 1]
        match = re.search(
            r"([A-Za-zÁÉÍÓÖŐÚÜŰáéíóöőúüű](?:\.[A-Za-zÁÉÍÓÖŐÚÜŰáéíóöőúüű])+\.?|[A-Za-zÁÉÍÓÖŐÚÜŰáéíóöőúüű]{1,10}\.)\W*$",
            prefix,
        )
        return match.group(1) if match else ""

    @staticmethod
    def _is_abbreviation_boundary(text: str, end_idx: int) -> bool:
        dotted = KnowledgeFacade._token_with_period_before(text, end_idx)
        if dotted:
            compact = dotted.replace(".", "").lower()
            if compact in KnowledgeFacade._SENTENCE_ABBREVIATIONS:
                return True
            if re.fullmatch(r"(?:[A-Za-z]\.){2,}[A-Za-z]?", dotted):
                return True
        prev_token_match = re.search(r"([A-Za-zÁÉÍÓÖŐÚÜŰáéíóöőúüű0-9]+)\W*$", text[: end_idx + 1])
        prev_token = prev_token_match.group(1).lower() if prev_token_match else ""
        return prev_token in KnowledgeFacade._SENTENCE_ABBREVIATIONS

    @staticmethod
    def _is_date_boundary(text: str, end_idx: int) -> bool:
        window_start = max(0, end_idx - 32)
        window_end = min(len(text), end_idx + 32)
        snippet = text[window_start:window_end]
        local_idx = end_idx - window_start
        next_token = KnowledgeFacade._next_token(text, end_idx + 1)
        for pattern in KnowledgeFacade._SENTENCE_DATE_PATTERNS:
            for match in pattern.finditer(snippet):
                match_start, match_end = match.span()
                if not (match_start <= local_idx < match_end):
                    continue
                last_non_space = match_end - 1
                while last_non_space >= match_start and snippet[last_non_space].isspace():
                    last_non_space -= 1
                # A dátum belsejében lévő pontok soha ne vágjanak.
                if local_idx < last_non_space:
                    return True
                # A teljes dátum utáni pont csak akkor vághat, ha utána erős új mondatkezdet látszik.
                return not (next_token and next_token[:1].isupper())
        return False

    @staticmethod
    def _is_dotted_abbreviation_continuation(text: str, end_idx: int) -> bool:
        return end_idx + 1 < len(text) and text[end_idx + 1].isalpha()

    @staticmethod
    def _is_legal_reference_boundary(text: str, end_idx: int) -> bool:
        return bool(re.match(r"\s*§", text[end_idx + 1 :]))

    @staticmethod
    def _is_numeric_list_boundary(text: str, end_idx: int) -> bool:
        return bool(KnowledgeFacade._NUMERIC_LIST_BOUNDARY_PATTERN.match(text[end_idx + 1 :]))

    @staticmethod
    def _is_marker_only_fragment(text: str, start_idx: int, end_idx: int) -> bool:
        fragment = str(text[start_idx : end_idx + 1] or "").strip()
        if not fragment:
            return False
        return bool(re.fullmatch(rf"(?:{KnowledgeFacade._SECTION_MARKER_TOKEN}\.)+", fragment, flags=re.IGNORECASE))

    @staticmethod
    def _split_heading_sentence_candidates(text: str) -> list[SentenceCandidate]:
        marker_match = KnowledgeFacade._HEADING_MARKER_PATTERN.match(text)
        if not marker_match:
            fallback_candidates = KnowledgeFacade._split_sentence_candidates(text, block_type="heading_fragment")
            if len(fallback_candidates) <= 1:
                candidate = KnowledgeFacade._build_sentence_candidate(
                    text, 0, len(text), confidence=0.95, split_reason="heading_block", block_type="heading"
                )
                return [candidate] if candidate else []
            result: list[SentenceCandidate] = []
            for candidate in fallback_candidates:
                mapped = KnowledgeFacade._build_sentence_candidate(
                    text,
                    candidate.char_start_offset,
                    candidate.char_end_offset,
                    confidence=candidate.confidence,
                    split_reason="heading_sentence" if candidate.split_reason == "strong_punctuation" else candidate.split_reason,
                    block_type="heading",
                )
                if mapped:
                    result.append(mapped)
            return result
        body_start = marker_match.end()
        raw_body = text[body_start:]
        body_left_trim = len(raw_body) - len(raw_body.lstrip())
        body_offset = body_start + body_left_trim
        body_text = text[body_offset:]
        if not body_text:
            candidate = KnowledgeFacade._build_sentence_candidate(
                text, 0, len(text), confidence=0.95, split_reason="heading_block", block_type="heading"
            )
            return [candidate] if candidate else []
        body_candidates = KnowledgeFacade._split_sentence_candidates(body_text, block_type="heading_fragment")
        if len(body_candidates) <= 1:
            candidate = KnowledgeFacade._build_sentence_candidate(
                text, 0, len(text), confidence=0.95, split_reason="heading_block", block_type="heading"
            )
            return [candidate] if candidate else []
        result: list[SentenceCandidate] = []
        for index, candidate in enumerate(body_candidates):
            mapped_start = 0 if index == 0 else body_offset + candidate.char_start_offset
            mapped_end = body_offset + candidate.char_end_offset
            mapped = KnowledgeFacade._build_sentence_candidate(
                text,
                mapped_start,
                mapped_end,
                confidence=candidate.confidence,
                split_reason="heading_sentence" if index == 0 else candidate.split_reason,
                block_type="heading",
            )
            if mapped:
                result.append(mapped)
        return result

    @staticmethod
    def _is_parenthesized_list_marker_start(text: str, marker_start: int) -> bool:
        prefix = text[:marker_start].rstrip()
        if not prefix:
            return False
        if prefix.endswith(("§", "bekezdés", "bek.", "pont", "alpont")):
            return False
        return True

    @staticmethod
    def _is_inline_heading_marker_start(text: str, marker_start: int, marker_end: int) -> bool:
        prefix = text[:marker_start].rstrip()
        if not prefix:
            return False
        if prefix.endswith(("§", "bekezdés", "bek.", "pont", "alpont", "pontja", "fejezete")):
            return False
        if KnowledgeFacade._sentence_word_count(prefix) < 2:
            return False
        next_token = KnowledgeFacade._next_token(text, marker_end)
        if not next_token or not next_token[:1].isupper():
            return False
        return True

    @staticmethod
    def _build_sentence_candidate(
        text: str,
        start: int,
        end: int,
        *,
        confidence: float,
        split_reason: str,
        block_type: str | None = None,
    ) -> SentenceCandidate | None:
        segment = text[start:end]
        if not segment:
            return None
        left_trim = len(segment) - len(segment.lstrip())
        right_trim = len(segment.rstrip())
        trimmed_start = start + left_trim
        trimmed_end = start + right_trim
        if trimmed_end <= trimmed_start:
            return None
        candidate_text = KnowledgeFacade._normalize_sentence_candidate_text(text[trimmed_start:trimmed_end])
        if not candidate_text:
            return None
        if block_type not in {"heading", "list_item", "heading_fragment", "list_item_fragment"} and KnowledgeFacade._looks_like_noise_sentence_candidate(candidate_text):
            return None
        return SentenceCandidate(
            text=candidate_text,
            confidence=max(0.0, min(0.99, round(confidence, 2))),
            split_reason=split_reason,
            char_start_offset=trimmed_start,
            char_end_offset=trimmed_end,
        )

    @staticmethod
    def _long_segment_break_index(text: str, start: int, end: int) -> int | None:
        segment = text[start:end]
        words = list(re.finditer(r"\b\w+\b", segment, flags=re.UNICODE))
        if len(words) < 30:
            return None
        midpoint = len(segment) // 2
        conjunction_matches = list(
            re.finditer(r"\b(?:és|vagy|de|illetve|azonban|viszont)\b", segment, flags=re.IGNORECASE | re.UNICODE)
        )
        preferred = [
            match.start()
            for match in conjunction_matches
            if int(len(segment) * 0.3) <= match.start() <= int(len(segment) * 0.7)
        ]
        if preferred:
            relative = min(preferred, key=lambda pos: abs(pos - midpoint))
            return start + relative
        whitespace_matches = [match.start() for match in re.finditer(r"\s+", segment)]
        if not whitespace_matches:
            return None
        relative = min(whitespace_matches, key=lambda pos: abs(pos - midpoint))
        return start + relative

    @staticmethod
    def _split_long_candidate(candidate: SentenceCandidate) -> list[SentenceCandidate]:
        if candidate.split_reason != "long_segment_fallback":
            return [candidate]
        if re.search(r"[.!?;:]", candidate.text):
            return [candidate]
        split_idx = KnowledgeFacade._long_segment_break_index(
            candidate.text,
            0,
            len(candidate.text),
        )
        if split_idx is None:
            return [candidate]
        left = KnowledgeFacade._build_sentence_candidate(
            candidate.text,
            0,
            split_idx,
            confidence=0.2,
            split_reason="long_segment_fallback",
        )
        right = KnowledgeFacade._build_sentence_candidate(
            candidate.text,
            split_idx,
            len(candidate.text),
            confidence=0.2,
            split_reason="long_segment_fallback",
        )
        parts = [part for part in (left, right) if part is not None]
        return parts or [candidate]

    @staticmethod
    def _split_sentence_candidates(text: str, *, block_type: str | None = None) -> list[SentenceCandidate]:
        normalized = str(text or "").strip()
        if not normalized:
            return []
        if block_type == "heading":
            return KnowledgeFacade._split_heading_sentence_candidates(normalized)
        if block_type in {"metadata", "noise", "footer"}:
            candidate = KnowledgeFacade._build_sentence_candidate(
                normalized, 0, len(normalized), confidence=0.25, split_reason="structure_block", block_type=block_type
            )
            return [candidate] if candidate else []
        if block_type == "list_item":
            result: list[SentenceCandidate] = []
            line_matches = list(re.finditer(r"[^\n]+", normalized))
            for match in line_matches or [re.match(r"[\s\S]+", normalized)]:
                if match is None:
                    continue
                line_start = match.start()
                line_end = match.end()
                line_text = normalized[line_start:line_end]
                line_candidates = KnowledgeFacade._split_sentence_candidates(line_text, block_type="list_item_fragment")
                if not line_candidates:
                    candidate = KnowledgeFacade._build_sentence_candidate(
                        normalized,
                        line_start,
                        line_end,
                        confidence=0.55,
                        split_reason="list_item_block",
                        block_type=block_type,
                    )
                    if candidate:
                        result.append(candidate)
                    continue
                for candidate in line_candidates:
                    mapped = KnowledgeFacade._build_sentence_candidate(
                        normalized,
                        line_start + candidate.char_start_offset,
                        line_start + candidate.char_end_offset,
                        confidence=candidate.confidence,
                        split_reason="list_item_line" if candidate.split_reason == "tail" else candidate.split_reason,
                        block_type=block_type,
                    )
                    if mapped:
                        result.append(mapped)
            return result
        if block_type == "table_row":
            candidate = KnowledgeFacade._build_sentence_candidate(
                normalized, 0, len(normalized), confidence=0.4, split_reason="table_row_block", block_type=block_type
            )
            return [candidate] if candidate else []

        candidates: list[SentenceCandidate] = []
        start = 0
        idx = 0
        text_length = len(normalized)
        paren_depth = 0

        def _append_candidate(end_idx: int, confidence: float, split_reason: str) -> None:
            nonlocal start
            split_end = end_idx
            while split_end < text_length and normalized[split_end] in "\"'”’)]}":
                split_end += 1
            candidate = KnowledgeFacade._build_sentence_candidate(
                normalized,
                start,
                split_end,
                confidence=confidence,
                split_reason=split_reason,
                block_type=block_type,
            )
            if candidate:
                candidates.append(candidate)
            start = split_end

        while idx < text_length:
            current = normalized[idx]
            if current in "([{":
                paren_depth += 1
            elif current in ")]}":
                paren_depth = max(0, paren_depth - 1)
            elif current in ".!?" and paren_depth == 0:
                next_token = KnowledgeFacade._next_token(normalized, idx + 1)
                capital_after = bool(next_token) and next_token[:1].isupper()
                if current == ".":
                    if (
                        KnowledgeFacade._is_dotted_abbreviation_continuation(normalized, idx)
                        or KnowledgeFacade._is_marker_only_fragment(normalized, start, idx)
                        or KnowledgeFacade._is_legal_reference_boundary(normalized, idx)
                    ):
                        idx += 1
                        continue
                    if KnowledgeFacade._is_numeric_list_boundary(normalized, idx):
                        _append_candidate(idx + 1, 0.72, "numeric_list_boundary")
                        idx = start
                        continue
                    if next_token and not capital_after:
                        idx += 1
                        continue
                if not KnowledgeFacade._is_abbreviation_boundary(normalized, idx) and not KnowledgeFacade._is_date_boundary(normalized, idx):
                    confidence = 0.6 + (0.2 if capital_after else 0.0)
                    _append_candidate(idx + 1, confidence, "strong_punctuation")
                    idx = start
                    continue
            elif current in ";:" and paren_depth == 0:
                next_token = KnowledgeFacade._next_token(normalized, idx + 1)
                capital_after = bool(next_token) and next_token[:1].isupper()
                if current == ";" and capital_after:
                    _append_candidate(idx + 1, 0.5 + 0.2, "medium_punctuation:semicolon")
                    idx = start
                    continue
                if current == ":" and capital_after:
                    _append_candidate(idx + 1, 0.45 + 0.2, "medium_punctuation:colon")
                    idx = start
                    continue
            elif current == "\n":
                line_break_end = idx
                while line_break_end < text_length and normalized[line_break_end] == "\n":
                    line_break_end += 1
                next_token = KnowledgeFacade._next_token(normalized, line_break_end)
                fragment = KnowledgeFacade._normalize_sentence_candidate_text(normalized[start:idx])
                if fragment and next_token:
                    confidence = 0.25
                    if next_token[:1].isupper():
                        confidence += 0.15
                    if len(fragment) <= 72 or KnowledgeFacade._sentence_word_count(fragment) <= 8:
                        confidence += 0.05
                    _append_candidate(idx, confidence, "newline_candidate")
                    idx = start
                    continue
            elif current.isspace():
                heading_match = KnowledgeFacade._INLINE_HEADING_MARKER_PATTERN.match(normalized, idx + 1)
                marker_match = KnowledgeFacade._LIST_MARKER_PAREN_PATTERN.match(normalized, idx + 1)
                fragment = KnowledgeFacade._normalize_sentence_candidate_text(normalized[start:idx])
                if (
                    heading_match
                    and fragment
                    and KnowledgeFacade._is_inline_heading_marker_start(normalized, heading_match.start(), heading_match.end())
                ):
                    _append_candidate(idx, 0.7, "hierarchical_marker")
                    idx = start
                    continue
                if marker_match and fragment and KnowledgeFacade._is_parenthesized_list_marker_start(normalized, marker_match.start()):
                    _append_candidate(idx, 0.55, "list_marker_parenthesized")
                    idx = start
                    continue
            idx += 1

        tail = KnowledgeFacade._build_sentence_candidate(
            normalized,
            start,
            text_length,
            confidence=0.4,
            split_reason="tail",
            block_type=block_type,
        )
        if tail:
            candidates.append(tail)

        final_candidates: list[SentenceCandidate] = []
        for candidate in candidates:
            final_candidates.extend(KnowledgeFacade._split_long_candidate(candidate))
        return final_candidates

    @staticmethod
    def _split_sentences(text: str, *, block_type: str | None = None) -> list[str]:
        return [candidate.text for candidate in KnowledgeFacade._split_sentence_candidates(text, block_type=block_type)]

    @staticmethod
    def _build_table_sentence_units(paragraph_text: str, paragraph_metadata: dict[str, Any]) -> list[dict[str, Any]]:
        table_cells = [str(cell).strip() for cell in paragraph_metadata.get("table_cells") or [] if str(cell).strip()]
        if not table_cells:
            return []
        if str(paragraph_metadata.get("table_role") or "") == "header":
            return []

        headers = [str(value).strip() for value in paragraph_metadata.get("table_column_headers") or [] if str(value).strip()]
        sentence_units: list[dict[str, Any]] = []
        search_cursor = 0
        for column_index, cell_text in enumerate(table_cells, start=1):
            cell_start = paragraph_text.find(cell_text, search_cursor)
            if cell_start < 0:
                cell_start = paragraph_text.find(cell_text)
            if cell_start < 0:
                continue
            cell_end = cell_start + len(cell_text)
            search_cursor = cell_end
            header_text = headers[column_index - 1] if column_index - 1 < len(headers) else ""
            display_text = f"{header_text}: {cell_text}" if header_text and header_text.lower() != cell_text.lower() else cell_text
            sentence_units.append(
                {
                    "text": display_text,
                    "char_start_offset": cell_start,
                    "char_end_offset": cell_end,
                    "metadata": {
                        "table_column_index": column_index,
                        "table_column_header": header_text or None,
                        "table_cell_text": cell_text,
                        "table_role": paragraph_metadata.get("table_role"),
                        "is_table_cell": True,
                    },
                }
            )
        return sentence_units

    @classmethod
    def _is_strong_sentence_candidate(cls, candidate: SentenceCandidate) -> bool:
        return candidate.confidence >= cls._CLAIM_STRONG_CONFIDENCE

    @classmethod
    def _build_claim_refinement_budget(cls, total_blocks: int) -> int:
        if total_blocks <= 0:
            return 0
        ratio_budget = max(1, int(total_blocks * cls._CLAIM_FINE_SPLIT_MAX_BLOCK_RATIO))
        return min(cls._CLAIM_FINE_SPLIT_MAX_BLOCKS_PER_DOCUMENT, ratio_budget)

    @classmethod
    def _count_claim_refinement_signals(cls, text: str) -> dict[str, int]:
        normalized = cls._normalize_sentence_candidate_text(text)
        lowered = normalized.lower()
        comma_count = normalized.count(",")
        connector_count = len(cls._CLAIM_FINE_SPLIT_CONNECTOR_PATTERN.findall(lowered))
        predicate_count = len(cls._CLAIM_FINE_SPLIT_PREDICATE_PATTERN.findall(lowered))
        punctuation_signal_count = int(";" in normalized) + int(":" in normalized) + int(comma_count >= 2)
        signal_score = punctuation_signal_count
        if connector_count >= 2:
            signal_score += 1
        if predicate_count >= 2:
            signal_score += 1
        if (" ha " in f" {lowered} " or "amennyiben" in lowered) and connector_count >= 1:
            signal_score += 1
        return {
            "word_count": cls._sentence_word_count(normalized),
            "connector_count": connector_count,
            "predicate_count": predicate_count,
            "punctuation_signal_count": punctuation_signal_count,
            "signal_score": signal_score,
        }

    @classmethod
    def _should_attempt_claim_refinement(
        cls,
        candidate: SentenceCandidate,
        *,
        block_type: str,
        refinement_state: dict[str, Any] | None = None,
    ) -> tuple[bool, str, dict[str, int]]:
        signals = cls._count_claim_refinement_signals(candidate.text)
        if block_type not in cls._CLAIM_FINE_SPLIT_ALLOWED_BLOCK_TYPES:
            return False, "unsupported_block_type", signals
        if signals["word_count"] < cls._CLAIM_FINE_SPLIT_MIN_WORDS:
            return False, "too_short", signals
        if signals["predicate_count"] == 0:
            return False, "no_predicate_signal", signals
        if signals["signal_score"] < cls._CLAIM_FINE_SPLIT_MIN_SIGNAL_SCORE:
            return False, "low_signal_score", signals
        if refinement_state is not None:
            attempted_blocks = int(refinement_state.get("attempted_blocks") or 0)
            hit_blocks = int(refinement_state.get("hit_blocks") or 0)
            budget_blocks = int(refinement_state.get("budget_blocks") or 0)
            if budget_blocks >= 0 and attempted_blocks >= budget_blocks:
                return False, "budget_exhausted", signals
            early_stop_after_blocks = int(
                refinement_state.get("early_stop_after_blocks") or cls._CLAIM_FINE_SPLIT_EARLY_STOP_AFTER_BLOCKS
            )
            min_hit_blocks_to_continue = int(
                refinement_state.get("min_hit_blocks_to_continue") or cls._CLAIM_FINE_SPLIT_MIN_HIT_BLOCKS_TO_CONTINUE
            )
            if attempted_blocks >= early_stop_after_blocks and hit_blocks < min_hit_blocks_to_continue:
                return False, "low_yield_early_stop", signals
        return True, "eligible", signals

    @staticmethod
    def _language_tag_from_metadata(metadata: dict[str, Any]) -> str | None:
        if not metadata:
            return None
        return metadata.get("language") or metadata.get("language_tag")

    @staticmethod
    def _sentence_unit_from_candidate(candidate: SentenceCandidate, *, strong_split: bool) -> dict[str, Any]:
        return {
            "text": candidate.text,
            "char_start_offset": candidate.char_start_offset,
            "char_end_offset": candidate.char_end_offset,
            "metadata": {
                "split_reason": candidate.split_reason,
                "split_confidence": candidate.confidence,
                "split_strength": "strong" if strong_split else "weak",
                "uncertain_split": not strong_split,
            },
        }

    def _refine_candidate_with_claim_splitter(
        self,
        paragraph_text: str,
        candidate: SentenceCandidate,
        *,
        paragraph_metadata: dict[str, Any],
    ) -> list[dict[str, Any]] | None:
        if not self._claim_fine_splitter:
            return None
        block_start = candidate.char_start_offset
        block_end = candidate.char_end_offset
        if block_start >= block_end:
            return None
        block_text = paragraph_text[block_start:block_end]
        if not block_text.strip():
            return None
        claim_candidates = self._claim_fine_splitter.split_block(
            block_text, language_tag=self._language_tag_from_metadata(paragraph_metadata)
        )
        if not claim_candidates:
            return None
        units: list[dict[str, Any]] = []
        for claim in claim_candidates:
            if claim.char_end <= claim.char_start:
                continue
            units.append(
                {
                    "text": claim.text_span,
                    "char_start_offset": block_start + claim.char_start,
                    "char_end_offset": block_start + claim.char_end,
                    "metadata": {
                        "split_reason": "claim_fine_split",
                        "claim_split_reasons": claim.split_reason,
                        "split_confidence": claim.confidence,
                        "split_strength": "claim_refined",
                        "uncertain_split": False,
                        "refined_from_reason": candidate.split_reason,
                        "refined_from_confidence": candidate.confidence,
                        "subject_hint": claim.subject_hint,
                        "predicate_hint": claim.predicate_hint,
                        "object_hint": claim.object_hint,
                    },
                }
            )
        return units or None

    def _build_sentence_units_for_paragraph(
        self,
        paragraph_text: str,
        *,
        block_type: str,
        paragraph_metadata: dict[str, Any],
        refinement_state: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        units, _diagnostics = self._build_sentence_units_for_paragraph_with_diagnostics(
            paragraph_text,
            block_type=block_type,
            paragraph_metadata=paragraph_metadata,
            refinement_state=refinement_state,
        )
        return units

    def _build_sentence_units_for_paragraph_with_diagnostics(
        self,
        paragraph_text: str,
        *,
        block_type: str,
        paragraph_metadata: dict[str, Any],
        refinement_state: dict[str, Any] | None = None,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        diagnostics: dict[str, Any] = {
            "block_type": block_type,
            "fallback_used": False,
            "candidate_count": 0,
            "strong_candidate_count": 0,
            "weak_candidate_count": 0,
            "claim_refinement_attempts": 0,
            "claim_refinement_hits": 0,
            "claim_refinement_units": 0,
            "claim_refinement_gate_reason": "not_needed",
            "claim_refinement_gate_reason_counts": {},
        }
        if block_type == "table_row":
            table_units = self._build_table_sentence_units(paragraph_text, paragraph_metadata)
            if table_units:
                diagnostics["candidate_count"] = len(table_units)
                diagnostics["strong_candidate_count"] = len(table_units)
                return table_units, diagnostics
        if block_type in {"metadata", "noise", "footer"}:
            diagnostics["candidate_count"] = 1 if paragraph_text else 0
            diagnostics["strong_candidate_count"] = diagnostics["candidate_count"]
            return [{"text": paragraph_text, "metadata": {}}], diagnostics
        candidates = self._split_sentence_candidates(paragraph_text, block_type=block_type)
        if not candidates:
            fallback = self._build_sentence_candidate(
                paragraph_text,
                0,
                len(paragraph_text),
                confidence=0.4,
                split_reason="fallback_single",
                block_type=block_type,
            )
            candidates = [fallback] if fallback else []
            diagnostics["fallback_used"] = bool(fallback)
        diagnostics["candidate_count"] = len(candidates)
        units: list[dict[str, Any]] = []
        block_refinement_attempted = False
        block_refinement_hit = False
        for candidate in candidates:
            strong = self._is_strong_sentence_candidate(candidate)
            if strong:
                diagnostics["strong_candidate_count"] += 1
            else:
                diagnostics["weak_candidate_count"] += 1
            if not strong and self._ENABLE_CLAIM_FINE_SPLIT_DURING_PARSING:
                should_attempt, gate_reason, signal_details = self._should_attempt_claim_refinement(
                    candidate,
                    block_type=block_type,
                    refinement_state=refinement_state,
                )
                diagnostics["claim_refinement_gate_reason"] = gate_reason
                gate_reason_counts = dict(diagnostics.get("claim_refinement_gate_reason_counts") or {})
                gate_reason_counts[gate_reason] = int(gate_reason_counts.get(gate_reason) or 0) + 1
                diagnostics["claim_refinement_gate_reason_counts"] = gate_reason_counts
                diagnostics["claim_refinement_signal_score"] = signal_details.get("signal_score")
                diagnostics["claim_refinement_predicate_count"] = signal_details.get("predicate_count")
                diagnostics["claim_refinement_connector_count"] = signal_details.get("connector_count")
                diagnostics["claim_refinement_punctuation_signal_count"] = signal_details.get("punctuation_signal_count")
                if should_attempt:
                    if refinement_state is not None and not block_refinement_attempted:
                        refinement_state["attempted_blocks"] = int(refinement_state.get("attempted_blocks") or 0) + 1
                    block_refinement_attempted = True
                    diagnostics["claim_refinement_attempts"] += 1
                    refined_units = self._refine_candidate_with_claim_splitter(
                        paragraph_text,
                        candidate,
                        paragraph_metadata=paragraph_metadata,
                    )
                    if refined_units:
                        diagnostics["claim_refinement_hits"] += 1
                        diagnostics["claim_refinement_units"] += len(refined_units)
                        block_refinement_hit = True
                        units.extend(refined_units)
                        continue
            units.append(self._sentence_unit_from_candidate(candidate, strong_split=strong))
        if refinement_state is not None and block_refinement_hit:
            refinement_state["hit_blocks"] = int(refinement_state.get("hit_blocks") or 0) + 1
        return units, diagnostics

    @staticmethod
    def _detect_assertion_mode(text: str) -> str:
        lowered = text.lower()
        if any(token in lowered for token in ("visszavon", "hatályon kívül", "érvényteleníti")):
            return "retraction"
        if any(token in lowered for token in ("helyesbít", "javít", "módosít", "pontosít")):
            return "correction"
        if any(token in lowered for token in ("talán", "valószínű", "feltételez", "elképzelhető")):
            return "uncertain"
        if any(token in lowered for token in ("vélemény", "szerintem", "úgy gondol", "megítélése")):
            return "opinion"
        if any(token in lowered for token in ("tervezi", "tervezett", "fog ", "majd ")) or " jövő" in lowered:
            return "plan"
        if any(token in lowered for token in ("nem ", "nincs", "tilos", "tagadja")):
            return "negation"
        if any(token in lowered for token in ("kell", "köteles", "jogosult", "felhatalmazza", "szükséges", "alkalmazandó", "kizárólag")):
            return "rule"
        if any(token in lowered for token in ("ha ", "amennyiben", "feltéve", "abban az esetben")):
            return "hypothesis"
        return "fact"

    @staticmethod
    def _detect_time_framing(text: str, *, assertion_mode: str) -> tuple[str, str | None]:
        lowered = text.lower()
        year_match = re.search(r"\b(19|20)\d{2}\.", text)
        if any(token in lowered for token in ("jelenleg", "most", "aktuálisan")):
            return "current", "aktuális"
        if any(token in lowered for token in ("volt", "korábban", "előző", "megelőző")):
            return "past", year_match.group(0) if year_match else "múltbeli"
        if any(token in lowered for token in ("lesz", "jövő", "majd", "tervezi", "fog ")) or assertion_mode == "plan":
            return "future", year_match.group(0) if year_match else "jövőbeli"
        if year_match:
            return "event", year_match.group(0)
        if assertion_mode in {"rule", "negation"}:
            return "timeless", "általános szabály"
        return "unknown", None

    @staticmethod
    def _detect_space_framing(text: str, mentions: list[Mention]) -> tuple[str, str | None]:
        lowered = text.lower()
        for mention in mentions:
            if mention.mention_type == "place":
                return "specific_place", mention.text_content
        if any(token in lowered for token in ("magyarország", "európai unió", "eu", "budapest")):
            return "jurisdiction", "Magyarország" if "magyarország" in lowered else "Európai Unió"
        if any(token in lowered for token in ("megállapodás", "szerződés", "megbízó", "alkusz", "társaság")):
            return "organization_scope", "szerződéses/organizációs tér"
        return "location_independent", None

    @staticmethod
    def _detect_claim_type(text: str, *, assertion_mode: str, mentions: list[Mention]) -> str:
        lowered = text.lower()
        if any(token in lowered for token in ("azonosító", "adószám", "számlaszám", "id", "uuid")):
            return "identifier"
        if assertion_mode in {"rule", "negation"} or any(token in lowered for token in ("ha ", "amennyiben", "feltétel")):
            return "rule_condition"
        if assertion_mode == "opinion":
            return "evaluative"
        if any(token in lowered for token in ("történt", "bekövetkezik", "létrejön", "megszűnik", "küld", "rögzít")):
            return "event"
        if len([mention for mention in mentions if mention.mention_type in {"person", "organization", "role", "system"}]) >= 2:
            return "relational"
        if any(token in lowered for token in ("van", "áll", "érvényes", "fennáll")):
            return "state"
        if any(token in lowered for token in ("minősül", "jelenti", "tartalmazza", "leírása")):
            return "stable_descriptor"
        return "other"

    @staticmethod
    def _mention_patterns() -> list[tuple[str, str]]:
        return [
            (
                "address",
                r"\b(?:ES-|HU-|DE-|FR-|IT-|PT-|RO-|PL-|AT-)?\d{4,5}\s+[A-ZÁÉÍÓÖŐÚÜŰ][\wÁÉÍÓÖŐÚÜŰáéíóöőúüű'’.\-]+(?:\s+[A-ZÁÉÍÓÖŐÚÜŰ][\wÁÉÍÓÖŐÚÜŰáéíóöőúüű'’.\-]+){0,3},?\s+(?:utca|u\.|út|útja|tér|köz|körút|lane|street|st\.|road|rd\.|avenue|ave\.|boulevard|blvd\.|calle|avenida|avda\.|plaza|piazza|via|straße|strasse|str\.|gasse|platz)\s+\d+[A-Za-z]?(?:/\d+)?(?:,?\s*(?:fszt\.?|emelet|em\.|ajtó|door|floor|apto\.?|apt\.?|wohnung|piso)\s*[\w/-]+)?\b",
            ),
            (
                "address",
                r"\b(?:Calle|Avenida|Avda\.|Plaza|Passeig|Via|Rue|Boulevard|Straße|Strasse|Street|Road|Avenue)\s+[A-ZÁÉÍÓÖŐÚÜŰ\wÁÉÍÓÖŐÚÜŰáéíóöőúüű'’.\-]+(?:\s+[A-ZÁÉÍÓÖŐÚÜŰ\wÁÉÍÓÖŐÚÜŰáéíóöőúüű'’.\-]+){0,5}\s+\d+[A-Za-z]?(?:/\d+)?(?:,?\s*(?:\d{4,5}\s+[A-ZÁÉÍÓÖŐÚÜŰ][\wÁÉÍÓÖŐÚÜŰáéíóöőúüű'’.\-]+(?:\s+[A-ZÁÉÍÓÖŐÚÜŰ][\wÁÉÍÓÖŐÚÜŰáéíóöőúüű'’.\-]+){0,3}))?(?:,?\s*(?:España|Spain|Hungary|Magyarország|Deutschland|Germany|France|Italia|Portugal|Polska|Romania|Austria))?\b",
            ),
            ("email", r"\b[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}\b"),
            ("phone_number", r"(?:(?<=\s)|^)(?:\+36|06)[\s\-()]?\d{1,2}[\s\-()]?\d{3}[\s\-()]?\d{3,4}(?=\s|$|[.,;])"),
            ("phone_number", r"(?:(?<=\s)|^)\+\d{2,3}[\s\-()]?\d{1,4}(?:[\s\-()]?\d{2,4}){2,4}(?=\s|$|[.,;])"),
            ("birth_date", r"\b(?:19|20)\d{2}\s*[./-]\s*(?:0?[1-9]|1[0-2])\s*[./-]\s*(?:0?[1-9]|[12]\d|3[01])\.?\b"),
            ("birth_date", r"\b(?:0?[1-9]|[12]\d|3[01])\s*[./-]\s*(?:0?[1-9]|1[0-2])\s*[./-]\s*(?:19|20)\d{2}\.?\b"),
            ("tax_id", r"\b\d{8}-\d-\d{2}\b"),
            ("spanish_nif", r"\b\d{8}[A-HJ-NP-TV-Z]\b"),
            ("spanish_nie", r"\b[XYZ]\d{7}[A-HJ-NP-TV-Z]\b"),
            ("spanish_cif", r"\b[A-HJNPQRSUVW]\d{7}[0-9A-J]\b"),
            (
                "eu_vat_number",
                r"\b(?:ATU\d{8}|BE0?\d{9}|BG\d{9,10}|CY\d{8}[A-Z]|CZ\d{8,10}|DE\d{9}|DK\d{8}|EE\d{9}|EL\d{9}|ES[A-Z0-9]\d{7}[A-Z0-9]|FI\d{8}|FR[A-HJ-NP-Z0-9]{2}\d{9}|HR\d{11}|HU\d{8}|IE\d[A-Z0-9*+]\d{5}[A-Z]{1,2}|IT\d{11}|LT(?:\d{9}|\d{12})|LU\d{8}|LV\d{11}|MT\d{8}|NL\d{9}B\d{2}|PL\d{10}|PT\d{9}|RO\d{2,10}|SE\d{12}|SI\d{8}|SK\d{10})\b",
            ),
            ("iban", r"\b[A-Z]{2}\d{2}(?:\s?[A-Z0-9]{4}){3,7}(?:\s?[A-Z0-9]{1,4})?\b"),
            ("bic_swift", r"\b[A-Z]{6}[A-Z0-9]{2}(?:[A-Z0-9]{3})?\b"),
            ("italian_codice_fiscale", r"\b[A-Z]{6}\d{2}[A-Z]\d{2}[A-Z]\d{3}[A-Z]\b"),
            ("french_siren", r"\b(?:SIREN[: ]*)?\d{9}\b"),
            ("french_siret", r"\b(?:SIRET[: ]*)?\d{14}\b"),
            ("polish_pesel", r"\b(?:PESEL[: ]*)?\d{11}\b"),
            ("romanian_cnp", r"\b(?:CNP[: ]*)?[1-8]\d{12}\b"),
            ("portuguese_nif", r"\b(?:NIF[: ]*)?\d{9}\b"),
            ("license_plate", r"\b[A-Z]{3}-\d{3}\b"),
            ("license_plate", r"\b[A-Z]{4}-\d{2}\b"),
            ("vin", r"\b[A-HJ-NPR-Z0-9]{17}\b"),
            ("traffic_permit_number", r"\b(?:forgalmi(?:\s+engedély)?\s*(?:szám|száma)?[: ]*)?[A-Z]{2}\d{6}\b"),
            ("driver_license_number", r"\b(?:jogosítvány(?:\s+szám|száma)?[: ]*)?[A-Z]{1,2}\d{6,8}\b"),
            ("social_security_number", r"\b\d{3}[ -]?\d{3}[ -]?\d{3}\b"),
            ("company_registration_number", r"\b\d{2}-\d{2}-\d{6}\b"),
            ("mixed_identifier", r"\b[A-Z0-9]{2,}(?:[-/][A-Z0-9]{2,})+\b"),
            ("mixed_identifier", r"\b[A-Z]{1,4}\d{2,}[A-Z0-9]*\b"),
            ("document_reference", r"\b\d{4}\.\s*évi\s+[IVXLCDM]+\.\s*törvény\b"),
            (
                "document_reference",
                r"\b\d+(?:/[A-Z])?\.\s*§(?:\s*\(\d+[a-z]?\))?(?:\s*(?:bekezdés|bek\.?))?(?:\s*[a-z]\))?(?:\s*(?:pont|alpont))?",
            ),
            ("document_reference", r"\b\d+(?:\.\d+){1,5}\.\b"),
            ("role", r"\b(?:Megbízó|Alkusz|Biztosító|Szolgáltató|Felhasználó|Megrendelő|Adatkezelő)\b"),
            ("organization", r"\b[A-ZÁÉÍÓÖŐÚÜŰ][\w.-]+(?:\s+[A-ZÁÉÍÓÖŐÚÜŰ][\w.-]+)*\s+(?:Kft\.|Zrt\.|Nyrt\.|Bt\.|GmbH|Ltd\.|Inc\.)(?=\s|$|[,;:])"),
            ("organization", r"\b[A-ZÁÉÍÓÖŐÚÜŰ][\w.&-]+(?:\s+[A-ZÁÉÍÓÖŐÚÜŰ][\w.&-]+){0,4}\s+(?:Kft\.|Zrt\.|Nyrt\.|Bt\.|Kht\.|Kkt\.|Egyesület|Alapítvány|Nonprofit\s+Kft\.)(?=\s|$|[,;:])"),
            ("system", r"\b[\w-]*(?:rendszer|platform|api|portál|alkalmazás)[\w-]*\b"),
            ("rule", r"\b(?:törvény|rendelet|szabályzat|ÁSZF|szabály)\b"),
            ("place", r"\b(?:Magyarország|Budapest|Európai Unió|EU)\b"),
        ]

    def _build_mentions_for_sentence(self, sentence: Sentence) -> list[Mention]:
        text = sentence.text_content
        mentions: list[Mention] = []
        seen_spans: set[tuple[int, int, str]] = set()

        def _overlaps_existing(char_start: int, char_end: int) -> bool:
            for existing_start, existing_end, _existing_type in seen_spans:
                if char_start < existing_end and char_end > existing_start:
                    return True
            return False

        for mention_type, pattern in self._mention_patterns():
            for match in re.finditer(pattern, text, flags=re.IGNORECASE):
                raw_match = match.group(0)
                if mention_type == "bic_swift" and raw_match.upper() != raw_match:
                    continue
                char_start = sentence.char_start + match.start()
                char_end = sentence.char_start + match.end()
                key = (char_start, char_end, mention_type)
                if key in seen_spans or _overlaps_existing(char_start, char_end):
                    continue
                seen_spans.add(key)
                normalized_value = raw_match.strip()
                if mention_type == "phone_number":
                    normalized_value = re.sub(r"\D+", "", normalized_value)
                elif mention_type in {
                    "spanish_nif",
                    "spanish_nie",
                    "spanish_cif",
                    "eu_vat_number",
                    "iban",
                    "bic_swift",
                    "italian_codice_fiscale",
                    "french_siren",
                    "french_siret",
                    "polish_pesel",
                    "romanian_cnp",
                    "portuguese_nif",
                    "birth_date",
                    "tax_id",
                    "license_plate",
                    "vin",
                    "traffic_permit_number",
                    "driver_license_number",
                    "social_security_number",
                    "company_registration_number",
                    "mixed_identifier",
                }:
                    normalized_value = normalized_value.upper()
                    if mention_type == "iban":
                        normalized_value = re.sub(r"\s+", "", normalized_value)
                mentions.append(
                    Mention(
                        tenant=sentence.tenant,
                        corpus_uuid=sentence.corpus_uuid,
                        source_id=sentence.source_id,
                        document_id=sentence.document_id,
                        sentence_id=sentence.id,
                        mention_type=mention_type,
                        text_content=raw_match,
                        normalized_value=normalized_value,
                        char_start=char_start,
                        char_end=char_end,
                        confidence=0.84 if mention_type in {"email", "phone_number", "birth_date", "tax_id", "vin", "iban", "eu_vat_number"} else 0.78 if mention_type in {"document_reference", "role", "address"} else 0.66,
                        metadata={"pattern": pattern},
                    )
                )

        for match in re.finditer(r"\b\d{5,}\b", text):
            raw_value = match.group(0)
            numeric_value = int(raw_value)
            if numeric_value % 100 == 0:
                continue
            char_start = sentence.char_start + match.start()
            char_end = sentence.char_start + match.end()
            if _overlaps_existing(char_start, char_end):
                continue
            mention_type = "generic_identifier"
            seen_spans.add((char_start, char_end, mention_type))
            mentions.append(
                Mention(
                    tenant=sentence.tenant,
                    corpus_uuid=sentence.corpus_uuid,
                    source_id=sentence.source_id,
                    document_id=sentence.document_id,
                    sentence_id=sentence.id,
                    mention_type=mention_type,
                    text_content=raw_value,
                    normalized_value=raw_value,
                    char_start=char_start,
                    char_end=char_end,
                    confidence=0.52,
                    metadata={"heuristic": "numeric_identifier_ge_5_not_divisible_by_100"},
                )
            )

        for match in re.finditer(r"\b[A-ZÁÉÍÓÖŐÚÜŰ][a-záéíóöőúüű]+(?:\s+[A-ZÁÉÍÓÖŐÚÜŰ][a-záéíóöőúüű]+){1,2}\b", text):
            phrase = match.group(0)
            char_start = sentence.char_start + match.start()
            char_end = sentence.char_start + match.end()
            if any(existing.text_content == phrase for existing in mentions) or _overlaps_existing(char_start, char_end):
                continue
            mention_type = "person"
            if any(token in phrase for token in ("Kft", "Zrt", "Bt", "Nyrt")):
                mention_type = "organization"
            seen_spans.add((char_start, char_end, mention_type))
            mentions.append(
                Mention(
                    tenant=sentence.tenant,
                    corpus_uuid=sentence.corpus_uuid,
                    source_id=sentence.source_id,
                    document_id=sentence.document_id,
                    sentence_id=sentence.id,
                    mention_type=mention_type,
                    text_content=phrase,
                    normalized_value=phrase,
                    char_start=char_start,
                    char_end=char_end,
                    confidence=0.58,
                    metadata={"heuristic": "capitalized_phrase"},
                )
            )
        return mentions

    @staticmethod
    def _align_extracted_mentions_to_sentence(sentence: Sentence, mentions: list[Mention]) -> list[Mention]:
        aligned: list[Mention] = []
        for item in mentions:
            aligned.append(
                replace(
                    item,
                    char_start=sentence.char_start + item.char_start,
                    char_end=sentence.char_start + item.char_end,
                    metadata={
                        **dict(item.metadata or {}),
                        "relative_char_start": item.char_start,
                        "relative_char_end": item.char_end,
                        "char_offset_mode": "sentence_relative_extractor_input",
                    },
                )
            )
        return aligned

    @staticmethod
    def _merge_sentence_mentions(extracted_mentions: list[Mention], heuristic_mentions: list[Mention]) -> list[Mention]:
        merged: list[Mention] = []

        def _priority(item: Mention) -> tuple[int, int, int]:
            mention_type = str(item.mention_type or "")
            type_rank = {
                "location": 0,
                "module": 1,
                "software": 2,
                "process": 3,
                "organization": 4,
                "company": 4,
                "person": 5,
                "unknown": 9,
            }.get(mention_type, 8)
            return (type_rank, -(item.char_end - item.char_start), item.char_start)

        def _overlaps(left: Mention, right: Mention) -> bool:
            return left.char_start < right.char_end and left.char_end > right.char_start

        for item in [*extracted_mentions, *heuristic_mentions]:
            duplicate_idx = next(
                (
                    index
                    for index, existing in enumerate(merged)
                    if existing.text_content == item.text_content
                    and existing.char_start == item.char_start
                    and existing.char_end == item.char_end
                ),
                None,
            )
            if duplicate_idx is not None:
                if _priority(item) < _priority(merged[duplicate_idx]):
                    merged[duplicate_idx] = item
                continue
            shadowed_by: int | None = None
            should_skip = False
            for index, existing in enumerate(merged):
                if not _overlaps(item, existing):
                    continue
                if _priority(existing) <= _priority(item):
                    should_skip = True
                    break
                shadowed_by = index
                break
            if should_skip:
                continue
            if shadowed_by is not None:
                merged[shadowed_by] = item
            else:
                merged.append(item)
        return sorted(merged, key=lambda item: (item.char_start, item.char_end, item.text_content))

    @staticmethod
    def _is_mention_debug_enabled(*, source: Source | None, document: Document | None, sentence: Sentence) -> bool:
        return bool(
            getattr(settings, "DEBUG_MENTION", False)
            or getattr(settings, "debug_mention", False)
            or sentence.metadata.get("mention_debug")
            or sentence.metadata.get("debug_mentions")
            or getattr(document, "metadata", {}).get("mention_debug")
            or getattr(source, "metadata", {}).get("mention_debug")
        )

    @staticmethod
    def _is_claim_debug_enabled(*, source: Source | None, document: Document | None, sentence: Sentence) -> bool:
        return bool(
            getattr(settings, "DEBUG_CLAIM", False)
            or getattr(settings, "debug_claim", False)
            or sentence.metadata.get("claim_debug")
            or sentence.metadata.get("debug_claims")
            or getattr(document, "metadata", {}).get("claim_debug")
            or getattr(source, "metadata", {}).get("claim_debug")
        )

    @staticmethod
    def _is_space_time_debug_enabled(*, source: Source | None, document: Document | None, sentence: Sentence) -> bool:
        return bool(
            getattr(settings, "DEBUG_SPACE_TIME", False)
            or getattr(settings, "debug_space_time", False)
            or sentence.metadata.get("space_time_debug")
            or sentence.metadata.get("debug_space_time")
            or getattr(document, "metadata", {}).get("space_time_debug")
            or getattr(source, "metadata", {}).get("space_time_debug")
        )

    @staticmethod
    def _claim_extractor_version() -> str:
        version = str(getattr(settings, "CLAIM_EXTRACTOR_VERSION", "legacy") or "legacy").strip().lower()
        return version if version in {"legacy", "v1"} else "legacy"

    @staticmethod
    def _resolve_sentence_language(
        sentence: Sentence,
        *,
        source: Source | None = None,
        document: Document | None = None,
    ) -> str:
        source_language = None
        if source is not None and isinstance(source.metadata, dict):
            source_language = source.metadata.get("language") or source.metadata.get("language_tag")
        preferred_language = (
            sentence.metadata.get("language")
            or sentence.metadata.get("language_tag")
            or getattr(document, "language", None)
            or source_language
        )
        return detect_language(sentence.text_content, preferred_language=preferred_language) or resolve_language(
            text=sentence.text_content,
            language=preferred_language,
        )

    def _build_sentence_mentions(
        self,
        sentence: Sentence,
        *,
        source: Source | None = None,
        document: Document | None = None,
    ) -> list[Mention]:
        language = self._resolve_sentence_language(sentence, source=source, document=document)
        extracted_mentions = self._align_extracted_mentions_to_sentence(
            sentence,
            self._mention_extractor.extract(sentence, language=language),
        )
        heuristic_mentions = self._build_mentions_for_sentence(sentence)
        heuristic_mentions = [
            replace(
                item,
                metadata={
                    **dict(item.metadata or {}),
                    "language": language,
                },
            )
            for item in heuristic_mentions
        ]
        sentence_mentions = self._merge_sentence_mentions(extracted_mentions, heuristic_mentions)
        logger.debug(
            "[MENTION PIPELINE]\nsentence_id=%s\nmention_count=%s",
            sentence.id,
            len(sentence_mentions),
        )
        if self._is_mention_debug_enabled(source=source, document=document, sentence=sentence):
            debug_print_mentions(sentence, sentence_mentions, language=language)
        return sentence_mentions

    def _build_space_time_frames_for_claims(
        self,
        *,
        sentence: Sentence,
        claims: list[Claim],
        language: str,
        source: Source | None = None,
        document: Document | None = None,
        emit_logs: bool = True,
    ) -> tuple[list[Claim], list[SpaceTimeFrame]]:
        updated_claims: list[Claim] = []
        frames: list[SpaceTimeFrame] = []
        for claim in claims:
            updated_claim, frame = self.build_and_attach_space_time_frame(
                claim=claim,
                sentence=sentence,
                language=language,
                source=source,
                document=document,
                emit_logs=emit_logs,
            )
            updated_claims.append(updated_claim)
            frames.append(frame)
        return updated_claims, frames

    def build_and_attach_space_time_frame(
        self,
        *,
        claim: Claim,
        sentence: Sentence,
        language: str,
        source: Source | None = None,
        document: Document | None = None,
        emit_logs: bool = True,
    ) -> tuple[Claim, SpaceTimeFrame]:
        frame = self._space_time_extractor_v1.extract(claim, sentence, language=language)
        if claim.space_time_frame_id:
            frame = replace(frame, id=claim.space_time_frame_id)
        updated_claim = replace(
            claim,
            space_time_frame_id=frame.frame_id,
            time_mode=frame.time_mode,
            time_label=frame.time_value,
            space_mode=frame.space_mode,
            space_label=frame.space_value,
            metadata={
                **dict(claim.metadata or {}),
                "space_time_frame_id": frame.frame_id,
                "space_time_language": frame.language,
                "space_time_frame_time_mode": frame.time_mode,
                "space_time_frame_space_mode": frame.space_mode,
                "space_time_frame_confidence": frame.overall_confidence,
            },
        )
        if emit_logs:
            logger.debug(
                "[SPACE-TIME PIPELINE]\nsentence_id=%s\nclaim_id=%s\nframe_id=%s\ntime_mode=%s\nspace_mode=%s\nconfidence=%s",
                sentence.id,
                updated_claim.claim_id,
                frame.frame_id,
                frame.time_mode,
                frame.space_mode,
                frame.overall_confidence,
            )
            if self._is_space_time_debug_enabled(source=source, document=document, sentence=sentence):
                SpaceTimeExtractorV1.debug_print(updated_claim, frame)
        return updated_claim, frame

    def _build_sentence_claim_payload(
        self,
        sentence: Sentence,
        mentions: list[Mention],
        *,
        source: Source | None = None,
        document: Document | None = None,
        defer_space_time: bool = False,
    ) -> tuple[SentenceInterpretation, list[Claim], list[SpaceTimeFrame]]:
        legacy_interpretation, legacy_claims = self._build_claim_for_sentence(sentence, mentions)
        language = self._resolve_sentence_language(sentence, source=source, document=document)
        version = self._claim_extractor_version()
        if version != "v1":
            logger.debug(
                "[CLAIM PIPELINE]\nsentence_id=%s\nmention_count=%s\nclaim_count=%s",
                sentence.id,
                len(mentions),
                len(legacy_claims),
            )
            return (
                replace(
                    legacy_interpretation,
                    metadata={
                        **legacy_interpretation.metadata,
                        "claim_extractor_version": "legacy",
                        "language": language,
                    },
                ),
                legacy_claims,
                [],
            )

        claims, claim_quality = run_v1_sentence_claim_pipeline(
            sentence=sentence,
            mentions=mentions,
            resolved_language=language,
            extractor=self._claim_extractor_v1,
            quality_gate=self._claim_quality_gate,
        )
        logger.debug(
            "[CLAIM QUALITY GATE]\nsentence_id=%s\nraw_claim_count=%s\naccepted_claim_count=%s\nrejected_claim_count=%s\nskipped=%s\nsentence_reason=%s",
            sentence.id,
            int(claim_quality.get("generated_claim_count") or 0),
            len(claims),
            int(claim_quality.get("rejected_claim_count") or 0),
            bool(claim_quality.get("skipped")),
            claim_quality.get("sentence_reason"),
        )
        for rejected in list(claim_quality.get("rejected_claims") or []):
            logger.debug(
                "[CLAIM REJECTED]\nsentence_id=%s\nreason=%s\nextraction_pattern=%s\nextraction_language=%s\nsubject=%s\npredicate=%s\nobject=%s",
                sentence.id,
                rejected.get("reason"),
                rejected.get("extraction_pattern") or rejected.get("pattern_name"),
                rejected.get("extraction_language"),
                rejected.get("subject_text"),
                rejected.get("predicate"),
                rejected.get("object_text"),
            )
        if self._is_claim_debug_enabled(source=source, document=document, sentence=sentence):
            ClaimExtractorV1.debug_print(sentence, claims, language=language)
            for claim in claims:
                debug_claim_type(claim)

        if not claims:
            logger.debug(
                "[CLAIM PIPELINE]\nsentence_id=%s\nmention_count=%s\nclaim_count=%s",
                sentence.id,
                len(mentions),
                0,
            )
            return (
                replace(
                    legacy_interpretation,
                    metadata={
                        **legacy_interpretation.metadata,
                        "claim_extractor_version": "v1",
                        "space_time_frame_status": "empty",
                        "language": language,
                        "quality_gate": claim_quality,
                    },
                ),
                [],
                [],
            )

        if defer_space_time:
            primary_claim = claims[0]
            interpretation = replace(
                legacy_interpretation,
                claim_summary=primary_claim.claim_text or legacy_interpretation.claim_summary,
                claim_type=primary_claim.claim_type,
                confidence=max(float(legacy_interpretation.confidence or 0.0), float(primary_claim.confidence or 0.0)),
                metadata={
                    **legacy_interpretation.metadata,
                    "claim_extractor_version": "v1",
                    "space_time_frame_status": "pending",
                    "language": language,
                    "quality_gate": claim_quality,
                },
            )
            return interpretation, claims, []

        claims, space_time_frames = self._build_space_time_frames_for_claims(
            sentence=sentence,
            claims=claims,
            language=language,
            source=source,
            document=document,
        )
        primary_claim = claims[0]
        interpretation = replace(
            legacy_interpretation,
            claim_summary=primary_claim.claim_text or legacy_interpretation.claim_summary,
            claim_type=primary_claim.claim_type,
            confidence=max(float(legacy_interpretation.confidence or 0.0), float(primary_claim.confidence or 0.0)),
            metadata={
                **legacy_interpretation.metadata,
                "claim_extractor_version": "v1",
                "space_time_frame_status": "created" if space_time_frames else "empty",
                "space_time_frame_ids": [item.frame_id for item in space_time_frames],
                "language": language,
                "quality_gate": claim_quality,
            },
        )
        information_value_score, information_value_status, information_value_reason = self._score_information_value(
            sentence=sentence,
            mentions=mentions,
            claim=primary_claim,
            interpretation=interpretation,
        )
        interpretation = replace(
            interpretation,
            information_value_score=information_value_score,
            information_value_status=information_value_status,
            information_value_reason=information_value_reason,
            metadata={
                **interpretation.metadata,
                "information_value_score": information_value_score,
                "information_value_status": information_value_status,
                "information_value_reason": information_value_reason,
            },
        )
        logger.debug(
            "[CLAIM PIPELINE]\nsentence_id=%s\nmention_count=%s\nclaim_count=%s",
            sentence.id,
            len(mentions),
            len(claims),
        )
        return interpretation, claims, space_time_frames

    def _finalize_sentence_after_subject_context(
        self,
        sentence: Sentence,
        mentions: list[Mention],
        interpretation: SentenceInterpretation,
        claims: list[Claim],
        *,
        language: str,
        source: Source | None = None,
        document: Document | None = None,
    ) -> tuple[SentenceInterpretation, list[Claim], list[SpaceTimeFrame]]:
        """Subject context után: space–time keretek + information value (v1 claim pipeline)."""
        if not claims:
            return (
                replace(
                    interpretation,
                    metadata={
                        **interpretation.metadata,
                        "space_time_frame_status": "empty",
                    },
                ),
                claims,
                [],
            )

        claims, space_time_frames = self._build_space_time_frames_for_claims(
            sentence=sentence,
            claims=claims,
            language=language,
            source=source,
            document=document,
        )
        primary_claim = claims[0]
        interpretation = replace(
            interpretation,
            claim_summary=primary_claim.claim_text or interpretation.claim_summary,
            claim_type=primary_claim.claim_type,
            confidence=max(float(interpretation.confidence or 0.0), float(primary_claim.confidence or 0.0)),
            metadata={
                **interpretation.metadata,
                "space_time_frame_status": "created" if space_time_frames else "empty",
                "space_time_frame_ids": [item.frame_id for item in space_time_frames],
                "language": language,
            },
        )
        information_value_score, information_value_status, information_value_reason = self._score_information_value(
            sentence=sentence,
            mentions=mentions,
            claim=primary_claim,
            interpretation=interpretation,
        )
        interpretation = replace(
            interpretation,
            information_value_score=information_value_score,
            information_value_status=information_value_status,
            information_value_reason=information_value_reason,
            metadata={
                **interpretation.metadata,
                "information_value_score": information_value_score,
                "information_value_status": information_value_status,
                "information_value_reason": information_value_reason,
            },
        )
        logger.debug(
            "[CLAIM PIPELINE]\nsentence_id=%s\nmention_count=%s\nclaim_count=%s",
            sentence.id,
            len(mentions),
            len(claims),
        )
        return interpretation, claims, space_time_frames

    def get_ingest_run_trace(
        self,
        run_id: str,
        *,
        log_level: str | None = "FULL_TRACE",
        debug: bool = False,
    ) -> dict[str, Any] | None:
        return self._trace_service.build_trace(run_id, log_level=log_level, debug=debug)

    def _log_ingest_trace_summary(self, run_id: str) -> None:
        trace = self.get_ingest_run_trace(run_id)
        if trace is None:
            return
        summary = trace.get("summary") or {}
        logger.debug(
            "[KNOWLEDGE TRACE SUMMARY]\nrun_id=%s\nsource_id=%s\nlanguage=%s\nsentence_count=%s\nmention_count=%s\nclaim_count=%s\nspace_time_frame_count=%s\nlocal_entity_cluster_count=%s\nlocal_entity_count=%s\nlow_coherence_local_entity_count=%s\nunknown_entity_type_count=%s",
            trace["run_id"],
            trace.get("source_id"),
            trace.get("language", "unknown"),
            summary.get("sentence_count", 0),
            summary.get("mention_count", 0),
            summary.get("claim_count", 0),
            summary.get("space_time_frame_count", 0),
            summary.get("local_entity_cluster_count", 0),
            summary.get("local_entity_count", 0),
            summary.get("low_coherence_local_entity_count", 0),
            summary.get("unknown_entity_type_count", 0),
        )

    @staticmethod
    def _detect_predicate(text: str) -> tuple[str, int]:
        predicate_patterns = [
            r"\b(felhatalmazza|köteles|jogosult|rögzítse|rögzíti|alkalmazandó|küldi|küld|lehet|kell|van|áll|minősül|érvényes|tervezi|visszavonja|módosítja)\b",
        ]
        for pattern in predicate_patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                return match.group(1), match.start()
        words = text.split()
        if len(words) >= 2:
            return words[1], text.find(words[1])
        return text.strip(), 0

    def _build_claim_for_sentence(self, sentence: Sentence, mentions: list[Mention]) -> tuple[SentenceInterpretation, list[Claim]]:
        text = sentence.text_content.strip()
        block_type = str(sentence.metadata.get("block_type") or "")
        header_context_text = str(sentence.metadata.get("header_context_text") or "").strip()
        metadata_kind = str(sentence.metadata.get("metadata_kind") or "").strip()
        if block_type in {"metadata", "noise"}:
            interpretation = SentenceInterpretation(
                tenant=sentence.tenant,
                corpus_uuid=sentence.corpus_uuid,
                source_id=sentence.source_id,
                document_id=sentence.document_id,
                sentence_id=sentence.id,
                sentence_text=text,
                claim_summary=text,
                assertion_mode="ignored_structure",
                claim_type=metadata_kind or block_type,
                time_mode="unknown",
                time_label=None,
                space_mode="unknown",
                space_label=None,
                confidence=0.2,
                metadata={
                    "sentence_order": sentence.order_index,
                    "block_type": block_type,
                    "metadata_kind": metadata_kind or None,
                    "page_number": sentence.metadata.get("page_number"),
                    "interpretation_skipped": True,
                    "skip_reason": metadata_kind or block_type,
                },
            )
            information_value_score, information_value_status, information_value_reason = self._score_information_value(
                sentence=sentence,
                mentions=[],
                claim=None,
                interpretation=interpretation,
            )
            interpretation = replace(
                interpretation,
                information_value_score=information_value_score,
                information_value_status=information_value_status,
                information_value_reason=information_value_reason,
                metadata={
                    **interpretation.metadata,
                    "information_value_score": information_value_score,
                    "information_value_status": information_value_status,
                    "information_value_reason": information_value_reason,
                },
            )
            return interpretation, []
        if block_type == "heading":
            interpretation = SentenceInterpretation(
                tenant=sentence.tenant,
                corpus_uuid=sentence.corpus_uuid,
                source_id=sentence.source_id,
                document_id=sentence.document_id,
                sentence_id=sentence.id,
                sentence_text=text,
                claim_summary=text,
                assertion_mode="context_header",
                claim_type="context_header",
                time_mode="location_independent",
                time_label=None,
                space_mode="location_independent",
                space_label=None,
                confidence=0.82,
                metadata={
                    "sentence_order": sentence.order_index,
                    "block_type": block_type,
                    "page_number": sentence.metadata.get("page_number"),
                    "header_scope": "section_context",
                    "is_contextual_header": True,
                },
            )
            information_value_score, information_value_status, information_value_reason = self._score_information_value(
                sentence=sentence,
                mentions=mentions,
                claim=None,
                interpretation=interpretation,
            )
            interpretation = replace(
                interpretation,
                information_value_score=information_value_score,
                information_value_status=information_value_status,
                information_value_reason=information_value_reason,
                metadata={
                    **interpretation.metadata,
                    "information_value_score": information_value_score,
                    "information_value_status": information_value_status,
                    "information_value_reason": information_value_reason,
                },
            )
            return interpretation, []
        assertion_mode = self._detect_assertion_mode(text)
        time_mode, time_label = self._detect_time_framing(text, assertion_mode=assertion_mode)
        space_mode, space_label = self._detect_space_framing(text, mentions)
        claim_type = self._detect_claim_type(text, assertion_mode=assertion_mode, mentions=mentions)
        predicate_text, predicate_idx = self._detect_predicate(text)
        subject_text = ""
        object_text: str | None = None

        if mentions:
            subject_candidates = [item for item in mentions if item.mention_type in {"person", "organization", "role", "system"}]
            if subject_candidates:
                subject_text = subject_candidates[0].text_content
        if not subject_text and predicate_idx > 0:
            subject_text = text[:predicate_idx].strip(" ,;:-")
        if not subject_text:
            subject_text = text.split()[0] if text.split() else text
        predicate_end = predicate_idx + len(predicate_text)
        if predicate_end < len(text):
            object_text = text[predicate_end:].strip(" ,;:-") or None
        if not object_text and len(text.split()) > 2:
            object_text = " ".join(text.split()[2:]) or None

        summary = " ".join(part for part in [subject_text, predicate_text, object_text] if part).strip()
        interpretation = SentenceInterpretation(
            tenant=sentence.tenant,
            corpus_uuid=sentence.corpus_uuid,
            source_id=sentence.source_id,
            document_id=sentence.document_id,
            sentence_id=sentence.id,
            sentence_text=text,
            claim_summary=summary or text,
            assertion_mode=assertion_mode,
            claim_type=claim_type,
            time_mode=time_mode,
            time_label=time_label,
            space_mode=space_mode,
            space_label=space_label,
            confidence=0.72,
            metadata={
                "sentence_order": sentence.order_index,
                "block_type": block_type,
                "page_number": sentence.metadata.get("page_number"),
                "header_context_text": header_context_text or None,
                "header_context_sentence_id": sentence.metadata.get("header_context_sentence_id"),
                "header_context_paragraph_id": sentence.metadata.get("header_context_paragraph_id"),
            },
        )
        claim = Claim(
            tenant=sentence.tenant,
            corpus_uuid=sentence.corpus_uuid,
            source_id=sentence.source_id,
            document_id=sentence.document_id,
            sentence_id=sentence.id,
            subject_text=subject_text,
            predicate_text=predicate_text,
            object_text=object_text,
            claim_type=claim_type,
            assertion_mode=assertion_mode,
            time_mode=time_mode,
            time_label=time_label,
            space_mode=space_mode,
            space_label=space_label,
            confidence=0.69,
            metadata={"mention_count": len(mentions)},
        )
        information_value_score, information_value_status, information_value_reason = self._score_information_value(
            sentence=sentence,
            mentions=mentions,
            claim=claim,
            interpretation=interpretation,
        )
        interpretation = replace(
            interpretation,
            information_value_score=information_value_score,
            information_value_status=information_value_status,
            information_value_reason=information_value_reason,
            metadata={
                **interpretation.metadata,
                "information_value_score": information_value_score,
                "information_value_status": information_value_status,
                "information_value_reason": information_value_reason,
            },
        )
        return interpretation, [claim]

    def _build_sentence_interpretation_payload(self, sentence: Sentence) -> dict[str, Any]:
        mentions = self._build_sentence_mentions(sentence)
        interpretation, claims, _ = self._build_sentence_claim_payload(
            sentence,
            mentions,
            defer_space_time=True,
        )
        language = str(interpretation.metadata.get("language") or self._resolve_sentence_language(sentence))
        resolved = SubjectContextResolverV1().resolve_claims(
            [
                {
                    "sentence_id": sentence.id,
                    "order_index": sentence.order_index,
                    "text": sentence.text_content,
                    "language": language,
                    "mentions": mentions,
                    "claims": claims,
                }
            ]
        )
        claims = list(resolved[0].get("claims") or [])
        interpretation, claims, frames = self._finalize_sentence_after_subject_context(
            sentence,
            mentions,
            interpretation,
            claims,
            language=language,
            source=None,
            document=None,
        )
        return {
            "interpretation": interpretation,
            "mentions": mentions,
            "claims": claims,
            "space_time_frames": frames,
        }

    def _score_information_value(
        self,
        *,
        sentence: Sentence,
        mentions: list[Mention],
        claim: Claim | None,
        interpretation: SentenceInterpretation,
    ) -> tuple[float, str, str]:
        text = sentence.text_content.strip()
        lowered = text.lower()
        tokens = [token for token in re.findall(r"\b\w+\b", text, flags=re.UNICODE) if token]
        token_count = len(tokens)
        score = 0.5
        reasons: list[str] = []
        block_type = str(sentence.metadata.get("block_type") or "")
        header_context_text = str(sentence.metadata.get("header_context_text") or "").strip()
        metadata_kind = str(sentence.metadata.get("metadata_kind") or "").strip()

        if block_type == "heading":
            score = 8.0 if token_count >= 2 else 6.5
            reasons.append("szakasz_fejlec_kontextus")
            if mentions:
                score += min(0.8, 0.3 + len(mentions) * 0.2)
                reasons.append("fejlecben_van_mention")
            score = max(0.0, min(10.0, round(score, 2)))
            return score, "context_strong", "header_context_without_direct_claim"
        if block_type == "metadata":
            if metadata_kind == "table_of_contents":
                return 0.0, "discard_candidate", "table_of_contents_not_interpreted"
            return 1.0, "discard_candidate", "metadata_not_interpreted"
        if block_type == "noise":
            return 0.0, "discard_candidate", "noise_not_interpreted"

        has_subject = bool(claim and claim.subject_text and claim.subject_text.strip())
        has_predicate = bool(claim and claim.predicate_text and claim.predicate_text.strip())
        has_object = bool(claim and claim.object_text and str(claim.object_text).strip())
        if has_subject:
            score += 2.0
            reasons.append("van_subject")
        if has_predicate:
            score += 2.0
            reasons.append("van_predicate")
        if has_object:
            score += 1.5
            reasons.append("van_object")
        if mentions:
            score += min(1.5, 0.6 + len(mentions) * 0.25)
            reasons.append("van_mention")
        if interpretation.claim_type != "other":
            score += 1.0
            reasons.append("tipizalhato_claim")
        if interpretation.assertion_mode in {"rule", "fact", "negation"}:
            score += 0.8
            reasons.append("egyertelmu_allitasmod")
        if interpretation.time_mode != "unknown":
            score += 0.5
            reasons.append("van_idokeret")
        if interpretation.space_mode not in {"unknown", "location_independent"}:
            score += 0.5
            reasons.append("van_terkeret")
        if token_count >= 8:
            score += 0.8
            reasons.append("eleg_hosszu")
        if header_context_text:
            score += 1.2
            reasons.append("fejlec_kontextus")

        fragment_leads = (
            "és ",
            "valamint ",
            "illetve ",
            "vagy ",
            "de ",
            "azonban ",
            "amely ",
            "amelyet ",
            "mely ",
            "melyet ",
            "hogy ",
            "így ",
            "továbbá ",
            "részére ",
            "az alábbiak szerint",
        )
        starts_like_fragment = lowered.startswith(fragment_leads)
        if token_count < 3:
            score -= 3.0
            reasons.append("nagyon_rovid")
        elif token_count < 5:
            score -= 1.5
            reasons.append("rovid")
        if starts_like_fragment:
            score -= 2.2
            reasons.append("toredekes_kezdete")
            if token_count <= 4 and not header_context_text:
                score -= 1.8
                reasons.append("rovid_kontextusfuggo_toredek")
        if not has_predicate:
            score -= 2.4
            reasons.append("nincs_onallo_predicate")
        if not has_object and token_count < 6:
            score -= 1.0
            reasons.append("gyenge_allitasmag")
        if block_type in {"heading", "metadata", "noise", "footer"}:
            score -= 2.5
            reasons.append("nem_tudaselem_blokk")
        if re.fullmatch(r"[\d.\-() /]+", text):
            score -= 4.0
            reasons.append("puszta_hivatkozas")
        if re.match(r"^\s*\d+(?:\.\d+){0,5}\.?\s*$", text):
            score -= 3.5
            reasons.append("csak_sorszam")

        score = max(0.0, min(10.0, round(score, 2)))
        if score < 3.0:
            status = "merge_with_previous" if starts_like_fragment or token_count < 5 else "discard_candidate"
        elif score < 5.0:
            status = "weak"
        elif score < 7.5:
            status = "usable"
        else:
            status = "strong"

        if score < 3.0 and starts_like_fragment:
            reason = "fragment_without_independent_predicate"
        elif score < 3.0:
            reason = "low_information_density"
        elif score < 5.0:
            reason = "partial_claim_with_context_dependency"
        elif score < 7.5:
            reason = "usable_claim"
        else:
            reason = "high_information_claim"
        return score, status, reason

    def _resolve_and_persist_local_entity_clusters(
        self,
        *,
        run: InterpretationRun,
        source: Source,
        document: Document,
        sentences: list[Sentence],
        mentions: list[Mention],
        claims: list[Claim],
    ) -> tuple[list[LocalEntityCluster], dict[str, Any]]:
        """Claim / mention / space-time persist után: lokális entitás klaszterek + opcionális DB mentés.

        Újrafuttatás / idempotencia: mentés előtt ``delete_by_run`` (ha a run UUID), különben
        ``delete_by_source``, hogy ne duplikálódjanak a sorok.
        """
        run_uuid = uuid_lib.UUID(run.id) if _is_uuid_string(run.id) else None
        source_uuid = uuid_lib.UUID(source.id) if _is_uuid_string(source.id) else None
        source_language = (
            document.language
            or getattr(source, "language", None)
            or resolve_language(text=sentences[0].text_content if sentences else None)
        )
        local_clusters, local_resolver_trace = self._local_resolver_v1.resolve_with_trace(
            run_uuid,
            source_uuid,
            sentences,
            mentions,
            claims,
            language=source_language,
        )
        logger.debug(
            "[LOCAL RESOLVER V1]\ninterpretation_run_id=%s\ncluster_count=%s\nclaim_count=%s",
            run.id,
            len(local_clusters),
            len(claims),
        )
        repo = self._local_entity_cluster_repository
        if repo is None:
            return local_clusters, local_resolver_trace
        try:
            if run_uuid is not None:
                repo.delete_by_run(run_uuid)
            elif source_uuid is not None:
                repo.delete_by_source(source_uuid)
            if local_clusters:
                repo.save_many(local_clusters)
        except ProgrammingError as exc:
            if self._is_missing_table_error(exc, "knowledge_local_entity_clusters"):
                logger.warning(
                    "knowledge.local_entity_clusters.skip_missing_table",
                    extra={
                        "document_id": document.id,
                        "interpretation_run_id": run.id,
                        "source_id": source.id,
                    },
                )
            else:
                raise
        return local_clusters, local_resolver_trace

    def _interpret_document(
        self,
        *,
        source: Source,
        document: Document,
        sentences: list[Sentence],
        created_by: int | None = None,
        progress_callback: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> InterpretationRun | None:
        if (
            self._interpretation_run_store is None
            or self._sentence_interpretation_store is None
            or self._mention_store is None
            or self._claim_store is None
        ):
            if progress_callback is not None:
                progress_callback(
                    "interpretation_skipped",
                    {"reason": "stores_unavailable", "total_sentences": len(sentences)},
                )
            return None

        try:
            existing_run = self._interpretation_run_store.get_for_document(document.id)
        except ProgrammingError as exc:
            if self._is_missing_table_error(
                exc,
                "knowledge_interpretation_runs",
                "knowledge_sentence_interpretations",
                "knowledge_mentions",
                "knowledge_claims",
                "knowledge_space_time_frames",
            ):
                logger.warning(
                    "knowledge.interpretation.skip_missing_tables",
                    extra={"document_id": document.id, "source_id": source.id, "corpus_uuid": source.corpus_uuid},
                )
                if progress_callback is not None:
                    progress_callback(
                        "interpretation_skipped",
                        {"reason": "missing_tables", "total_sentences": len(sentences)},
                    )
                return None
            raise
        if existing_run is not None:
            if progress_callback is not None:
                progress_callback(
                    "interpretation_completed",
                    {
                        "interpretation_run_id": existing_run.id,
                        "processed_sentences": int(existing_run.metadata.get("sentence_interpretation_count") or len(sentences)),
                        "total_sentences": int(existing_run.metadata.get("sentence_count") or len(sentences)),
                        "mention_count": int(existing_run.metadata.get("mention_count") or 0),
                        "claim_count": int(existing_run.metadata.get("claim_count") or 0),
                        "local_entity_cluster_count": int(existing_run.metadata.get("local_entity_cluster_count") or 0),
                        "quality": dict(existing_run.metadata.get("quality_summary") or {}),
                    },
                )
            return existing_run

        run: InterpretationRun | None = None
        try:
            run = self._interpretation_run_store.create(
                InterpretationRun(
                    tenant=source.tenant,
                    corpus_uuid=source.corpus_uuid,
                    source_id=source.id,
                    document_id=document.id,
                    status="processing",
                    created_by=created_by,
                    started_at=_utcnow(),
                    metadata={"sentence_count": len(sentences)},
                )
            )
            if progress_callback is not None:
                progress_callback(
                    "interpretation_started",
                    {
                        "interpretation_run_id": run.id,
                        "processed_sentences": 0,
                        "total_sentences": len(sentences),
                    },
                )
            mentions: list[Mention] = []
            quality_summary = _empty_claim_quality_summary()
            staged: list[tuple[Sentence, list[Mention], SentenceInterpretation, str, list[Claim]]] = []
            for index, sentence in enumerate(sentences, start=1):
                sentence_mentions = self._build_sentence_mentions(sentence, source=source, document=document)
                sentence_language = self._resolve_sentence_language(sentence, source=source, document=document)
                sentence_interpretation, sentence_claims, _ = self._build_sentence_claim_payload(
                    sentence,
                    sentence_mentions,
                    source=source,
                    document=document,
                    defer_space_time=True,
                )
                sentence_interpretation = replace(sentence_interpretation, interpretation_run_id=run.id)
                sentence_mentions = [replace(item, interpretation_run_id=run.id) for item in sentence_mentions]
                sentence_claims = [replace(item, interpretation_run_id=run.id) for item in sentence_claims]
                quality_summary = _merge_claim_quality_summary(
                    quality_summary,
                    dict(sentence_interpretation.metadata.get("quality_gate") or {}),
                )
                staged.append((sentence, sentence_mentions, sentence_interpretation, sentence_language, sentence_claims))
                mentions.extend(sentence_mentions)
                if progress_callback is not None:
                    progress_callback(
                        "interpretation_progress",
                        {
                            "interpretation_run_id": run.id,
                            "processed_sentences": index,
                            "total_sentences": len(sentences),
                        },
                    )

            subject_context_payload: list[dict[str, Any]] = [
                {
                    "sentence_id": s.id,
                    "order_index": s.order_index,
                    "text": s.text_content,
                    "language": lang,
                    "mentions": sm,
                    "claims": sc,
                }
                for s, sm, _interp, lang, sc in staged
            ]
            resolved_subject_rows = SubjectContextResolverV1().resolve_claims(subject_context_payload)
            resolved_by_sid = {str(r.get("sentence_id") or ""): r for r in resolved_subject_rows}

            interpretations: list[SentenceInterpretation] = []
            claims: list[Claim] = []
            space_time_frames: list[SpaceTimeFrame] = []
            for sentence, sentence_mentions, sentence_interpretation, sentence_language, _ in staged:
                row = resolved_by_sid.get(str(sentence.id))
                sentence_claims = list((row or {}).get("claims") or [])
                interp_out, claims_out, frames_out = self._finalize_sentence_after_subject_context(
                    sentence,
                    sentence_mentions,
                    sentence_interpretation,
                    sentence_claims,
                    language=sentence_language,
                    source=source,
                    document=document,
                )
                interpretations.append(interp_out)
                claims.extend(claims_out)
                space_time_frames.extend(frames_out)

            created_interpretations = self._sentence_interpretation_store.create_many(interpretations)
            self._mention_store.create_many(mentions)
            self._claim_store.create_many(claims)
            if self._space_time_frame_store is not None:
                self._space_time_frame_store.create_many(space_time_frames)
            local_clusters, local_resolver_trace = self._resolve_and_persist_local_entity_clusters(
                run=run,
                source=source,
                document=document,
                sentences=sentences,
                mentions=mentions,
                claims=claims,
            )
            semantic_blocks = SemanticBlockBuilderV1().build(sentences=sentences, claims=claims)
            semantic_block_payload = [semantic_block_to_json_dict(item) for item in semantic_blocks]
            semantic_block_payload = enrich_semantic_blocks_with_quality(
                semantic_block_payload,
                existing_blocks=self._load_existing_semantic_blocks(
                    corpus_uuid=source.corpus_uuid,
                    exclude_interpretation_run_id=run.id,
                ),
                source_type=source.source_type,
            )
            technical_entities = TechnicalEntityBuilderV1().build(local_clusters, claims=claims)
            technical_entity_payload = [technical_entity_to_json_dict(item) for item in technical_entities]
            technical_memory_chunks = TechnicalMemoryChunkBuilderV1().build_many(technical_entities)
            technical_memory_chunk_payload = [
                technical_memory_chunk_to_json_dict(item) for item in technical_memory_chunks
            ]
            search_profiles = SearchProfileBuilderV1().build_many(technical_memory_chunks)
            search_profile_payload = [search_profile_to_json_dict(item) for item in search_profiles]
            stored_search_profiles = self._load_existing_search_profiles(
                corpus_uuid=source.corpus_uuid,
                exclude_interpretation_run_id=run.id,
            )
            stored_global_profiles = self._load_existing_global_profiles(
                corpus_uuid=source.corpus_uuid,
                exclude_interpretation_run_id=run.id,
            )
            candidate_profile_pool = stored_search_profiles or search_profiles
            candidate_selection_attempted_count = candidate_selection_attempt_count(
                search_profiles,
                existing_profiles=stored_search_profiles if stored_search_profiles else None,
            )
            candidate_pool_size = len(candidate_profile_pool)
            candidate_selections = CandidateSelectionV1().select_many(
                search_profiles,
                existing_profiles=stored_search_profiles if stored_search_profiles else None,
                limit_per_profile=3,
            )
            candidate_selection_payload = [entity_candidate_to_json_dict(item) for item in candidate_selections]
            similarity_analyses = SimilarityEngineV1().analyze_many(
                search_profiles,
                candidate_selections,
                candidate_profile_pool,
            )
            similarity_analysis_payload = [similarity_analysis_to_json_dict(item) for item in similarity_analyses]
            decision_analyses = DecisionEngineV1().decide_many(
                search_profiles,
                candidate_selections,
                similarity_analyses,
                tensions=[],
            )
            decision_analysis_payload = [decision_analysis_to_json_dict(item) for item in decision_analyses]
            global_profiles = GlobalProfileBuilderV0().build_many(
                decision_analyses,
                search_profiles,
                candidate_profiles=candidate_profile_pool,
                existing_global_profiles=stored_global_profiles,
            )
            tension_analyses = [
                *TensionEngineV1().analyze_many(
                    search_profiles,
                    similarity_analyses,
                    candidate_profile_pool,
                ),
                *TensionEngineV1().analyze_global_profiles(global_profiles),
            ]
            tension_analysis_payload = [tension_analysis_to_json_dict(item) for item in tension_analyses]
            retrieval_chunks = RetrievalChunkBuilderV0().build_many(
                global_profiles,
                tension_analysis_payload,
            )
            completed_run = self._interpretation_run_store.update(
                replace(
                    run,
                    status="completed",
                    language=document.language,
                    completed_at=_utcnow(),
                    updated_at=_utcnow(),
                    metadata=attach_local_resolver_metadata(
                        {
                            **run.metadata,
                            "sentence_interpretation_count": len(created_interpretations),
                            "mention_count": len(mentions),
                            "claim_count": len(claims),
                            "space_time_frame_count": len(space_time_frames),
                            "quality_summary": quality_summary,
                            "semantic_block_builder_version": SemanticBlockBuilderV1.version,
                            "semantic_block_count": len(semantic_blocks),
                            "semantic_blocks": semantic_block_payload,
                            "semantic_block_conflict_count": sum(int(item.get("conflict_count") or 0) for item in semantic_block_payload),
                            "semantic_block_disputed_count": sum(1 for item in semantic_block_payload if item.get("block_status") == "disputed"),
                            "technical_entity_builder_version": TechnicalEntityBuilderV1.version,
                            "technical_entity_count": len(technical_entities),
                            "technical_entities": technical_entity_payload,
                            "technical_memory_chunk_builder_version": TechnicalMemoryChunkBuilderV1.version,
                            "technical_memory_chunk_count": len(technical_memory_chunks),
                            "technical_memory_chunks": technical_memory_chunk_payload,
                            "search_profile_builder_version": SearchProfileBuilderV1.version,
                            "search_profile_count": len(search_profiles),
                            "search_profiles": search_profile_payload,
                            "candidate_selection_builder_version": CandidateSelectionV1.version,
                            "candidate_selection_attempted_count": candidate_selection_attempted_count,
                            "candidate_pool_size": candidate_pool_size,
                            "candidate_selection_count": len(candidate_selections),
                            "candidate_selections": candidate_selection_payload,
                            "similarity_engine_version": SimilarityEngineV1.version,
                            "similarity_analysis_count": len(similarity_analyses),
                            "similarity_analyses": similarity_analysis_payload,
                            "tension_engine_version": TensionEngineV1.version,
                            "tension_analysis_count": len(tension_analyses),
                            "tension_analyses": tension_analysis_payload,
                            "retrieval_chunk_builder_version": RetrievalChunkBuilderV0.version,
                            "retrieval_chunk_count": len(retrieval_chunks),
                            "retrieval_chunks": retrieval_chunks,
                            "decision_engine_version": DecisionEngineV1.version,
                            "decision_analysis_count": len(decision_analyses),
                            "decision_analyses": decision_analysis_payload,
                            "global_profile_builder_version": GlobalProfileBuilderV0.version,
                            "global_profile_count": len(global_profiles),
                            "global_profiles": global_profiles,
                        },
                        clusters=local_clusters,
                        trace=local_resolver_trace,
                    ),
                )
            )
            if progress_callback is not None:
                progress_callback(
                    "interpretation_completed",
                    {
                        "interpretation_run_id": completed_run.id,
                        "processed_sentences": len(created_interpretations),
                        "total_sentences": len(sentences),
                        "mention_count": len(mentions),
                        "claim_count": len(claims),
                        "local_entity_cluster_count": len(local_clusters),
                        "quality": quality_summary,
                    },
                )
            return completed_run
        except ProgrammingError as exc:
            if self._is_missing_table_error(
                exc,
                "knowledge_interpretation_runs",
                "knowledge_sentence_interpretations",
                "knowledge_mentions",
                "knowledge_claims",
            ):
                logger.warning(
                    "knowledge.interpretation.skip_missing_tables",
                    extra={"document_id": document.id, "source_id": source.id, "corpus_uuid": source.corpus_uuid},
                )
                if progress_callback is not None:
                    progress_callback(
                        "interpretation_skipped",
                        {"reason": "missing_tables", "total_sentences": len(sentences)},
                    )
                return None
            raise
        except Exception as exc:
            if run is None:
                return None
            failed_run = self._interpretation_run_store.update(
                replace(
                    run,
                    status="failed",
                    error_message=self._truncate_error_message(
                        exc,
                        max_length=self._INTERPRETATION_ERROR_MESSAGE_MAX,
                    ),
                    completed_at=_utcnow(),
                    updated_at=_utcnow(),
                )
            )
            if progress_callback is not None:
                progress_callback(
                    "interpretation_failed",
                    {
                        "interpretation_run_id": failed_run.id,
                        "processed_sentences": int(failed_run.metadata.get("sentence_interpretation_count") or 0),
                        "total_sentences": len(sentences),
                        "error_message": failed_run.error_message,
                    },
                )
            return failed_run

    def _extract_parser_document_from_source(self, source: Source) -> ExtractedDocument:
        if source.source_type == "text":
            text = self._normalize_parser_text(source.raw_content)
            paragraphs = [ExtractedParagraph(text=text)] if text else []
            return ExtractedDocument(
                text_content=text,
                paragraphs=paragraphs,
                metadata={"source_type": source.source_type, "extraction_engine": "manual_text_v1"},
            )
        if source.source_type == "file":
            bucket_name = str(source.metadata.get("bucket_name") or "")
            object_key = str(source.metadata.get("object_key") or "")
            filename = str(source.file_ref or source.title or "upload.txt")
            if not bucket_name or not object_key:
                raise ValueError("A fájlforráshoz hiányzik az object storage referencia.")
            stored = self._object_storage.get_bytes(key=object_key, bucket=bucket_name)
            extracted = extract_document_from_upload(filename, stored.body)
            normalized_text = self._normalize_parser_text(extracted.text_content)
            normalized_paragraphs = [
                replace(paragraph, text=self._normalize_parser_text(paragraph.text))
                for paragraph in extracted.paragraphs
                if self._normalize_parser_text(paragraph.text)
            ]
            if not normalized_paragraphs and normalized_text:
                normalized_paragraphs = [ExtractedParagraph(text=normalized_text)]
            return ExtractedDocument(
                text_content=normalized_text,
                paragraphs=normalized_paragraphs,
                metadata={
                    **dict(extracted.metadata or {}),
                    "source_type": source.source_type,
                    "filename": filename,
                },
            )
        if source.source_type == "url":
            url = str(source.metadata.get("origin_url") or "")
            if not url:
                raise ValueError("A hivatkozás forráshoz hiányzik az URL.")
            response = requests.get(url, timeout=20)
            response.raise_for_status()
            html = unescape(response.text or "")
            text = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.IGNORECASE)
            text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.IGNORECASE)
            text = re.sub(r"<[^>]+>", " ", text)
            normalized = self._normalize_parser_text(text)
            return ExtractedDocument(
                text_content=normalized,
                paragraphs=[ExtractedParagraph(text=normalized)] if normalized else [],
                metadata={"source_type": source.source_type, "origin_url": url, "extraction_engine": "html_strip_v1"},
            )
        fallback_text = self._normalize_parser_text(source.raw_content)
        return ExtractedDocument(
            text_content=fallback_text,
            paragraphs=[ExtractedParagraph(text=fallback_text)] if fallback_text else [],
            metadata={"source_type": source.source_type, "extraction_engine": "fallback_text_v1"},
        )

    def _delete_source_parse_outputs(self, source_id: str) -> None:
        document = self._document_store.get_for_source(source_id)
        if document is not None:
            if self._space_time_frame_store is not None:
                self._delete_for_document_if_table_exists(
                    self._space_time_frame_store,
                    document.id,
                    table_name="knowledge_space_time_frames",
                )
            if self._claim_store is not None:
                self._delete_for_document_if_table_exists(
                    self._claim_store,
                    document.id,
                    table_name="knowledge_claims",
                )
            if self._mention_store is not None:
                self._delete_for_document_if_table_exists(
                    self._mention_store,
                    document.id,
                    table_name="knowledge_mentions",
                )
            if self._sentence_interpretation_store is not None:
                self._delete_for_document_if_table_exists(
                    self._sentence_interpretation_store,
                    document.id,
                    table_name="knowledge_sentence_interpretations",
                )
            if self._interpretation_run_store is not None:
                self._delete_for_document_if_table_exists(
                    self._interpretation_run_store,
                    document.id,
                    table_name="knowledge_interpretation_runs",
                )
            self._sentence_store.delete_for_document(document.id)
            self._paragraph_store.delete_for_document(document.id)
            self._document_store.delete_for_source(source_id)
        self._parser_run_store.delete_for_source(source_id)

    def _is_stale_parser_processing(self, source_id: str, *, updated_at: datetime | None = None) -> bool:
        document = self._document_store.get_for_source(source_id)
        parser_run = self._parser_run_store.get_for_source(source_id)
        if document is None or parser_run is None or parser_run.status != "processing":
            return False
        if self._paragraph_store.list_for_document(document.id):
            return False
        if self._sentence_store.list_for_document(document.id):
            return False
        reference_time = updated_at or parser_run.updated_at or document.updated_at
        return (_utcnow() - reference_time).total_seconds() >= self._STALE_PARSER_RESTART_AFTER_SEC

    def _refresh_ingest_run(self, run_id: str) -> IngestRun:
        run = self._ingest_run_store.get(run_id)
        if run is None:
            raise ValueError(f"Ingest run not found: {run_id}")
        items = self._ingest_item_store.list_for_run(run_id)
        queued = sum(1 for item in items if item.status in {"received", "validated", "queued"})
        processing = sum(1 for item in items if item.status == "processing")
        completed = sum(1 for item in items if item.status == "completed")
        failed = sum(1 for item in items if item.status == "failed")
        duplicate = sum(1 for item in items if item.status == "duplicate")
        rejected = sum(1 for item in items if item.status == "rejected")
        if processing:
            status = "processing"
        elif failed and (completed or duplicate):
            status = "partial_success"
        elif failed:
            status = "failed"
        elif queued:
            status = "queued"
        else:
            status = "completed"
        refreshed = replace(
            run,
            status=status,  # type: ignore[arg-type]
            batch_size=len(items),
            queued_count=queued,
            processing_count=processing,
            completed_count=completed,
            failed_count=failed,
            duplicate_count=duplicate,
            rejected_count=rejected,
            updated_at=_utcnow(),
            completed_at=_utcnow() if status in {"completed", "partial_success", "failed"} and not queued and not processing else None,
            metadata={
                **dict(run.metadata or {}),
                "progress_summary": self._build_run_progress_summary(run, items),
                "quality_diagnostics": _aggregate_ingest_item_quality(items),
            },
        )
        return self._ingest_run_store.update(refreshed)

    def _require_corpus(self, corpus_uuid: str) -> Corpus:
        raw = self._corpus_store.get_by_uuid(corpus_uuid)
        if raw is None:
            raise ValueError("Corpus not found")
        return self._to_corpus(raw)

    def _ensure_title(self, value: str | None, *, fallback: str) -> str:
        normalized = str(value or "").strip()
        return (normalized or fallback)[:200]

    def _build_storage_key(self, *, tenant: str, run_id: str, item_id: str, filename: str) -> str:
        tenant_slug = (tenant or "default").strip() or "default"
        safe_filename = (filename or "upload.bin").strip().replace("/", "_")
        return self._object_storage.build_key(
            "tenants",
            tenant_slug,
            "knowledge",
            "ingest",
            run_id,
            item_id,
            "raw",
            safe_filename,
        )

    def _create_source_from_ingest_item(
        self,
        *,
        tenant: str,
        item: IngestItem,
        ingest_input: IngestInput,
        content_hash: str,
        created_by: int | None,
    ) -> Source:
        if ingest_input.input_type == "text":
            source = Source(
                tenant=tenant,
                corpus_uuid=item.corpus_uuid,
                title=item.title,
                source_type="text",
                raw_content=ingest_input.text_content,
                file_ref=None,
                status="attached",
                created_by=created_by,
                metadata={
                    "ingest_item_id": item.id,
                    "ingest_run_id": item.ingest_run_id,
                    "content_hash": content_hash,
                    "char_count": len(str(ingest_input.text_content or "")),
                },
            )
            return self._source_store.create(source)
        if ingest_input.input_type == "file":
            source = Source(
                tenant=tenant,
                corpus_uuid=item.corpus_uuid,
                title=item.title,
                source_type="file",
                raw_content=None,
                file_ref=ingest_input.original_filename,
                status="attached",
                created_by=created_by,
                metadata={
                    "ingest_item_id": item.id,
                    "ingest_run_id": item.ingest_run_id,
                    "content_hash": content_hash,
                    "storage_provider": ingest_input.storage_provider,
                    "bucket_name": ingest_input.bucket_name,
                    "object_key": ingest_input.object_key,
                    "mime_type": ingest_input.mime_type,
                    "size_bytes": ingest_input.size_bytes,
                    "checksum_sha256": ingest_input.checksum_sha256,
                },
            )
            return self._source_store.create(source)
        if ingest_input.input_type == "url":
            source = Source(
                tenant=tenant,
                corpus_uuid=item.corpus_uuid,
                title=item.title,
                source_type="url",
                raw_content=None,
                file_ref=None,
                status="attached",
                created_by=created_by,
                metadata={
                    "ingest_item_id": item.id,
                    "ingest_run_id": item.ingest_run_id,
                    "content_hash": content_hash,
                    "origin_url": ingest_input.origin_url,
                    "url_status_code": item.metadata.get("url_status_code"),
                    "url_content_type": item.metadata.get("url_content_type"),
                },
            )
            return self._source_store.create(source)
        raise ValueError(f"Unsupported source type for ingest input: {ingest_input.input_type}")

    def list_all(self, current_user_id: int | None = None, current_user: User | None = None) -> list[Corpus]:
        if current_user_id is None:
            return []
        all_kbs = [self._to_corpus(item) for item in self._corpus_store.list_all()]
        if has_permission(current_user, "knowledge.write"):
            return all_kbs
        permission = "train" if has_permission(current_user, "knowledge.permissions.manage") else "use"
        allowed_ids = set(self._corpus_store.get_kb_ids_with_permission(current_user_id, permission))
        return [kb for kb in all_kbs if kb.id is not None and kb.id in allowed_ids]

    def list_all_unfiltered(self) -> list[Corpus]:
        return [self._to_corpus(item) for item in self._corpus_store.list_all()]

    def qdrant_collection_for_uuid(self, kb_uuid: str) -> str | None:
        kb = self._corpus_store.get_by_uuid(kb_uuid)
        if not kb:
            return None
        return str(getattr(kb, "qdrant_collection_name"))

    def get_trainable_kb_ids(self, user_id: int, user: User | None) -> set[int]:
        if has_permission(user, "knowledge.write"):
            return {item.id for item in self.list_all_unfiltered() if item.id is not None}
        return set(self._corpus_store.get_kb_ids_with_permission(user_id, "train"))

    def create(
        self,
        name: str,
        description: str | None = None,
        permissions: list[tuple[int, str]] | None = None,
        current_user_id: int | None = None,
    ) -> Corpus:
        if self._corpus_store.get_by_name(name):
            raise ValueError("KB name already exists")
        if current_user_id is None:
            raise ValueError("Current user is required")
        corpus_uuid = str(uuid_lib.uuid4())
        corpus = Corpus(
            id=None,
            tenant="",
            uuid=corpus_uuid,
            name=name,
            description=description,
            qdrant_collection_name=f"kb_{corpus_uuid}",
            created_at=None,
            updated_at=None,
        )
        created_raw = self._corpus_store.create(corpus, actor_user_id=current_user_id)
        created = self._to_corpus(created_raw)
        perms = [(uid, perm) for uid, perm in (permissions or []) if perm and perm != "none"]
        if not any(uid == current_user_id for uid, _ in perms):
            perms.append((current_user_id, "train"))
        self._corpus_store.set_permissions(created.uuid, perms, actor_user_id=current_user_id)
        self._metrics_store.increment("corpus_count", 1)
        self._log_step("corpus.create", status="ok", corpus_uuid=created.uuid, permissions=len(perms))
        return created

    def update(
        self,
        uuid: str,
        name: str,
        description: str | None,
        personal_data_mode: str | None = None,
        current_user_id: int | None = None,
    ) -> Corpus:
        kb = self._corpus_store.get_by_uuid(uuid)
        if not kb:
            raise ValueError("KB not found")
        if current_user_id is None:
            raise ValueError("Current user is required")
        corpus = self._to_corpus(kb)
        updated = replace(
            corpus,
            name=name,
            description=description,
            personal_data_mode=personal_data_mode or corpus.personal_data_mode,
        )
        return self._to_corpus(self._corpus_store.update(updated, actor_user_id=current_user_id))

    def delete(self, uuid: str, confirm_name: str | None = None, demo_mode: bool = False) -> None:
        kb = self._corpus_store.get_by_uuid(uuid)
        if not kb:
            raise ValueError("KB not found")
        kb_name = str(getattr(kb, "name", "") or "")
        if demo_mode and kb_name.strip().lower() in self._DEMO_PROTECTED_KB_NAMES:
            raise ValueError("A teszt tudástár tesztüzemmódban nem törölhető.")
        if confirm_name and confirm_name != kb_name:
            raise ValueError("Confirmation name does not match")
        self._corpus_store.delete(uuid)
        self._log_step("corpus.delete", status="ok", corpus_uuid=uuid)

    def clear_contents(
        self,
        uuid: str,
        *,
        confirm_name: str | None = None,
        current_user_id: int | None = None,
    ) -> dict[str, int]:
        kb = self._corpus_store.get_by_uuid(uuid)
        if not kb:
            raise ValueError("KB not found")
        kb_name = str(getattr(kb, "name", "") or "")
        if confirm_name and confirm_name != kb_name:
            raise ValueError("Confirmation name does not match")

        file_objects = self._ingest_input_store.list_file_objects_for_corpus(uuid)
        build_collections = {
            str(item.collection_name).strip()
            for item in self._index_build_store.list_for_corpus(uuid)
            if str(item.collection_name).strip()
        }
        base_collection = str(getattr(kb, "qdrant_collection_name", "") or "").strip()
        if base_collection:
            build_collections.add(base_collection)

        deleted_objects = 0
        for bucket_name, object_key in file_objects:
            try:
                self._object_storage.delete_object(key=object_key, bucket=bucket_name)
                deleted_objects += 1
            except Exception:
                logger.warning(
                    "knowledge.clear_contents.object_delete_failed",
                    extra={"bucket": bucket_name, "object_key": object_key, "corpus_uuid": uuid},
                )

        deleted_collections = 0
        vector_index = self._vector_index_factory()
        for collection_name in build_collections:
            try:
                vector_index.delete_collection(collection_name)
                deleted_collections += 1
            except Exception:
                logger.warning(
                    "knowledge.clear_contents.collection_delete_failed",
                    extra={"collection_name": collection_name, "corpus_uuid": uuid},
                )

        deleted_events = self._ingest_event_store.delete_for_corpus(uuid)
        deleted_inputs = self._ingest_input_store.delete_for_corpus(uuid)
        deleted_items = self._ingest_item_store.delete_for_corpus(uuid)
        deleted_runs = self._ingest_run_store.delete_for_corpus(uuid)
        deleted_sentences = self._sentence_store.delete_for_corpus(uuid)
        deleted_paragraphs = self._paragraph_store.delete_for_corpus(uuid)
        deleted_documents = self._document_store.delete_for_corpus(uuid)
        deleted_parser_runs = self._parser_run_store.delete_for_corpus(uuid)
        deleted_claims = (
            self._delete_for_corpus_if_table_exists(self._claim_store, uuid, table_name="knowledge_claims")
            if self._claim_store is not None
            else 0
        )
        deleted_space_time_frames = (
            self._delete_for_corpus_if_table_exists(
                self._space_time_frame_store,
                uuid,
                table_name="knowledge_space_time_frames",
            )
            if self._space_time_frame_store is not None
            else 0
        )
        deleted_mentions = (
            self._delete_for_corpus_if_table_exists(self._mention_store, uuid, table_name="knowledge_mentions")
            if self._mention_store is not None
            else 0
        )
        deleted_sentence_interpretations = (
            self._delete_for_corpus_if_table_exists(
                self._sentence_interpretation_store,
                uuid,
                table_name="knowledge_sentence_interpretations",
            )
            if self._sentence_interpretation_store is not None
            else 0
        )
        deleted_interpretation_runs = (
            self._delete_for_corpus_if_table_exists(
                self._interpretation_run_store,
                uuid,
                table_name="knowledge_interpretation_runs",
            )
            if self._interpretation_run_store is not None
            else 0
        )
        deleted_query_runs = self._query_run_store.delete_for_corpus(uuid)
        deleted_sources = self._source_store.delete_for_corpus(uuid)
        deleted_builds = self._index_build_store.delete_for_corpus(uuid)

        result = {
            "sources": deleted_sources,
            "ingest_runs": deleted_runs,
            "ingest_items": deleted_items,
            "ingest_inputs": deleted_inputs,
            "ingest_events": deleted_events,
            "parser_runs": deleted_parser_runs,
            "documents": deleted_documents,
            "paragraphs": deleted_paragraphs,
            "sentences": deleted_sentences,
            "interpretation_runs": deleted_interpretation_runs,
            "sentence_interpretations": deleted_sentence_interpretations,
            "mentions": deleted_mentions,
            "claims": deleted_claims,
            "space_time_frames": deleted_space_time_frames,
            "index_builds": deleted_builds,
            "query_runs": deleted_query_runs,
            "storage_objects": deleted_objects,
            "vector_collections": deleted_collections,
        }
        self._log_step("corpus.clear_contents", status="ok", corpus_uuid=uuid, **result)
        return result

    def get_permissions_with_users(self, kb_uuid: str) -> list[dict[str, Any]]:
        perm_list = self._corpus_store.list_permissions(kb_uuid)
        perm_by_user = {uid: perm for uid, perm in perm_list}
        return [
            {
                "user_id": user.id,
                "email": getattr(user, "email", "") or "",
                "name": getattr(user, "name", None),
                "permission": perm_by_user.get(user.id, "none"),
                "role": getattr(user, "role", "user"),
            }
            for user in self._user_repo_list_all()
            if getattr(user, "id", None) is not None
        ]

    def get_permissions_with_users_batch(self, kb_uuids: list[str]) -> dict[str, list[dict[str, Any]]]:
        users = self._user_repo_list_all()
        perms_by_kb = self._corpus_store.list_permissions_batch(kb_uuids)
        result: dict[str, list[dict[str, Any]]] = {}
        for kb_uuid in kb_uuids:
            perm_by_user = {uid: perm for uid, perm in (perms_by_kb.get(kb_uuid) or [])}
            result[kb_uuid] = [
                {
                    "user_id": user.id,
                    "email": getattr(user, "email", "") or "",
                    "name": getattr(user, "name", None),
                    "permission": perm_by_user.get(user.id, "none"),
                    "role": getattr(user, "role", "user"),
                }
                for user in users
                if getattr(user, "id", None) is not None
            ]
        return result

    def set_permissions(
        self,
        kb_uuid: str,
        permissions: list[tuple[int, str]],
        current_user_id: int | None = None,
    ) -> None:
        if current_user_id is not None:
            existing = self._corpus_store.list_permissions(kb_uuid)
            existing_self = next((perm for uid, perm in existing if uid == current_user_id), "train")
            filtered = [(uid, perm) for uid, perm in permissions if uid != current_user_id and perm and perm != "none"]
            filtered.append((current_user_id, existing_self or "train"))
            self._corpus_store.set_permissions(kb_uuid, filtered, actor_user_id=current_user_id)
            return
        filtered = [(uid, perm) for uid, perm in permissions if perm and perm != "none"]
        self._corpus_store.set_permissions(kb_uuid, filtered, actor_user_id=0)

    def user_can_use(self, kb_uuid: str, user_id: int, user: User | None) -> bool:
        if has_permission(user, "knowledge.write"):
            return True
        kb = self._corpus_store.get_by_uuid(kb_uuid)
        if not kb or getattr(kb, "id", None) is None:
            return False
        return getattr(kb, "id") in self._corpus_store.get_kb_ids_with_permission(user_id, "use")

    def user_can_train(self, kb_uuid: str, user_id: int, user: User | None) -> bool:
        if has_permission(user, "knowledge.write"):
            return True
        kb = self._corpus_store.get_by_uuid(kb_uuid)
        if not kb or getattr(kb, "id", None) is None:
            return False
        return getattr(kb, "id") in self._corpus_store.get_kb_ids_with_permission(user_id, "train")

    def create_source(
        self,
        *,
        tenant: str,
        corpus_uuid: str,
        title: str,
        source_type: str,
        raw_content: str | None,
        file_ref: str | None,
        created_by: int | None,
    ) -> Source:
        source = Source(
            tenant=tenant,
            corpus_uuid=corpus_uuid,
            title=title,
            source_type=source_type,  # type: ignore[arg-type]
            raw_content=raw_content,
            file_ref=file_ref,
            status="attached",
            created_by=created_by,
            metadata={"content_length": len(raw_content or "")},
        )
        self._metrics_store.increment("source_count", 1)
        self._log_step("source.create", status="ok", tenant=tenant, corpus_uuid=corpus_uuid, source_id=source.id)
        return self._source_store.create(source)

    def list_sources(self, corpus_uuid: str) -> list[Source]:
        return self._source_store.list_for_corpus(corpus_uuid)

    def get_source(self, source_id: str) -> Source | None:
        return self._source_store.get(source_id)

    def get_source_content(self, source_id: str) -> dict[str, Any] | None:
        source = self._source_store.get(source_id)
        if source is None:
            return None
        document = self._document_store.get_for_source(source_id)
        return {
            "id": source.id,
            "corpus_uuid": source.corpus_uuid,
            "title": source.title,
            "source_type": source.source_type,
            "file_ref": source.file_ref,
            "original_content": source.raw_content,
            "extracted_text": document.text_content if document is not None else str(source.raw_content or ""),
            "metadata": source.metadata,
        }

    @staticmethod
    def _source_display_type(source: Source) -> str:
        if source.source_type == "text":
            return "Gépelés"
        filename = str(source.file_ref or source.title or "").lower()
        if filename.endswith(".pdf"):
            return "PDF"
        if filename.endswith(".docx"):
            return "DOCX"
        if filename.endswith(".doc"):
            return "DOC"
        if source.source_type == "url":
            return "URL"
        return "Fájl" if source.source_type == "file" else str(source.source_type or "")

    def _source_created_by_label(self, source: Source) -> str:
        if source.created_by is None:
            return "Ismeretlen"
        user = None
        if self._user_repo is not None and hasattr(self._user_repo, "get_by_id"):
            try:
                user = self._user_repo.get_by_id(source.created_by)
            except Exception:
                user = None
        for attr in ("full_name", "name", "email", "username"):
            value = getattr(user, attr, None) if user is not None else None
            if str(value or "").strip():
                return str(value).strip()
        return f"Felhasználó #{source.created_by}"

    @staticmethod
    def _download_filename(source: Source) -> str:
        filename = str(source.file_ref or source.title or source.id).strip() or source.id
        if source.source_type == "text" and "." not in filename.rsplit("/", 1)[-1]:
            filename = f"{filename}.txt"
        return filename

    def get_source_download(self, source_id: str) -> dict[str, Any] | None:
        source = self._source_store.get(source_id)
        if source is None:
            return None
        filename = self._download_filename(source)
        if source.source_type == "file":
            bucket_name = str(source.metadata.get("bucket_name") or "")
            object_key = str(source.metadata.get("object_key") or "")
            if not bucket_name or not object_key:
                return None
            stored = self._object_storage.get_bytes(key=object_key, bucket=bucket_name)
            return {
                "filename": filename,
                "content_type": stored.ref.content_type or source.metadata.get("mime_type") or "application/octet-stream",
                "body": stored.body,
            }
        document = self._document_store.get_for_source(source_id) if hasattr(self._document_store, "get_for_source") else None
        text = str(source.raw_content or (document.text_content if document is not None else "") or "")
        return {
            "filename": filename,
            "content_type": "text/plain; charset=utf-8",
            "body": text.encode("utf-8"),
        }

    def get_query_source_download(self, query_run_id: str, source_id: str) -> dict[str, Any] | None:
        run = self._query_run_store.get(query_run_id)
        if run is None:
            return None
        direct_download = self.get_source_download(source_id)
        if direct_download is not None:
            return direct_download

        citation = next(
            (
                item
                for item in run.citations
                if item.source_id == source_id or item.chunk_id == source_id
            ),
            None,
        )
        snippet = citation.snippet if citation is not None else ""
        if not snippet:
            snippet = run.context_text or ""
        answer_text = str(run.metadata.get("answer_text") or "")
        parts = [
            "AIPLAZA chat source context",
            f"Query run: {run.id}",
            f"Source id: {source_id}",
            f"Question: {run.query}",
            f"Answer: {answer_text}",
            "",
            "Context:",
            snippet,
        ]
        return {
            "filename": f"aiplaza-context-{source_id[:8] or run.id[:8]}.txt",
            "content_type": "text/plain; charset=utf-8",
            "body": "\n".join(parts).encode("utf-8"),
            "corpus_uuid": run.corpus_uuid,
        }

    def get_query_context_download(self, query_run_id: str) -> dict[str, Any] | None:
        run = self._query_run_store.get(query_run_id)
        if run is None:
            return None
        answer_text = str(run.metadata.get("answer_text") or "")
        parts = [
            "AIPLAZA LLM context audit",
            f"Query run: {run.id}",
            f"Corpus UUID: {run.corpus_uuid}",
            f"Question: {run.query}",
            f"Answer: {answer_text}",
            "",
            "LLM instructions:",
            (
                "A kovetkezo tudastar-context alapjan valaszolj tomoren, es csak akkor allits tenyt, "
                "ha a context alatamasztja. A valasz nyelve mindig egyezzen meg a felhasznalo kerdesenek nyelvevel."
            ),
            "",
            "Context sent to LLM:",
            run.context_text or "",
        ]
        return {
            "filename": f"aiplaza-llm-context-{run.id[:8]}.txt",
            "content_type": "text/plain; charset=utf-8",
            "body": "\n".join(parts).encode("utf-8"),
            "corpus_uuid": run.corpus_uuid,
        }

    def parse_source(
        self,
        source_id: str,
        *,
        created_by: int | None = None,
        progress_callback: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> ParserRun:
        source = self._source_store.get(source_id)
        if source is None:
            raise ValueError("Source not found")

        existing_document = self._document_store.get_for_source(source_id)
        if existing_document is not None:
            existing_run = self._parser_run_store.get_for_source(source_id)
            if existing_run is not None and existing_run.status == "completed":
                return existing_run
            logger.warning(
                "knowledge.parse_source.reset_incomplete_state",
                extra={
                    "source_id": source_id,
                    "existing_document_id": existing_document.id,
                    "existing_run_id": existing_run.id if existing_run is not None else None,
                    "existing_run_status": existing_run.status if existing_run is not None else None,
                },
            )
            self._delete_source_parse_outputs(source_id)

        parser_run = self._parser_run_store.create(
            ParserRun(
                tenant=source.tenant,
                corpus_uuid=source.corpus_uuid,
                source_id=source.id,
                status="processing",
                parser_type="basic_text_v1",
                created_by=created_by,
                started_at=_utcnow(),
                metadata={"source_type": source.source_type},
            )
        )
        if progress_callback is not None:
            progress_callback("parser_started", {"parser_run_id": parser_run.id})

        try:
            extracted_document = self._extract_parser_document_from_source(source)
            raw_text = extracted_document.text_content
            if not raw_text:
                raise ValueError(self._describe_empty_extraction(extracted_document.metadata))

            document = self._document_store.create(
                Document(
                    tenant=source.tenant,
                    corpus_uuid=source.corpus_uuid,
                    source_id=source.id,
                    parser_run_id=parser_run.id,
                    title=source.title,
                    language="hu",
                    text_content=raw_text,
                    char_count=len(raw_text),
                    status="ready",
                    metadata={
                        "source_type": source.source_type,
                        **dict(extracted_document.metadata or {}),
                    },
                )
            )

            paragraph_blocks = [
                paragraph
                for paragraph in extracted_document.paragraphs
                if self._normalize_parser_text(paragraph.text)
            ]
            if not paragraph_blocks:
                paragraph_texts = self._split_paragraphs(raw_text)
                if not paragraph_texts:
                    paragraph_texts = [raw_text]
                paragraph_blocks = [ExtractedParagraph(text=paragraph_text) for paragraph_text in paragraph_texts]

            paragraphs: list[Paragraph] = []
            sentences: list[Sentence] = []
            cursor = 0
            sentence_index = 1
            current_header_text: str | None = None
            current_header_paragraph_id: str | None = None
            current_header_sentence_id: str | None = None
            total_blocks = len(paragraph_blocks)
            claim_refinement_state = {
                "budget_blocks": self._build_claim_refinement_budget(total_blocks),
                "attempted_blocks": 0,
                "hit_blocks": 0,
                "early_stop_after_blocks": self._CLAIM_FINE_SPLIT_EARLY_STOP_AFTER_BLOCKS,
                "min_hit_blocks_to_continue": self._CLAIM_FINE_SPLIT_MIN_HIT_BLOCKS_TO_CONTINUE,
            }
            parser_block_stats = {
                "total_blocks": total_blocks,
                "blocks_started": 0,
                "blocks_completed": 0,
                "fine_split_budget_blocks": int(claim_refinement_state["budget_blocks"]),
                "fine_split_run_blocks": 0,
                "fine_split_not_run_blocks": 0,
                "fine_split_hit_blocks": 0,
            }
            for paragraph_index, paragraph_block in enumerate(paragraph_blocks, start=1):
                paragraph_text = self._normalize_parser_text(paragraph_block.text)
                start = raw_text.find(paragraph_text, cursor)
                if start < 0:
                    start = cursor
                end = start + len(paragraph_text)
                paragraph = Paragraph(
                    tenant=source.tenant,
                    corpus_uuid=source.corpus_uuid,
                    source_id=source.id,
                    document_id=document.id,
                    order_index=paragraph_index,
                    text_content=paragraph_text,
                    char_start=start,
                    char_end=end,
                    sentence_count=0,
                    metadata={
                        "block_type": paragraph_block.block_type,
                        "header_context_text": current_header_text if paragraph_block.block_type != "heading" else None,
                        "header_context_paragraph_id": current_header_paragraph_id if paragraph_block.block_type != "heading" else None,
                        "header_context_sentence_id": current_header_sentence_id if paragraph_block.block_type != "heading" else None,
                        "page_number": paragraph_block.page_number,
                        "bbox": list(paragraph_block.bbox) if paragraph_block.bbox else None,
                        "font_size": paragraph_block.font_size,
                        "is_bold": paragraph_block.is_bold,
                        **dict(paragraph_block.metadata or {}),
                    },
                )
                parser_block_stats["blocks_started"] += 1
                if progress_callback is not None:
                    progress_callback(
                        "parser_block_started",
                        {
                            "parser_run_id": parser_run.id,
                            "document_id": document.id,
                            "block_id": paragraph.id,
                            "block_index": paragraph_index,
                            "total_blocks": total_blocks,
                            "block_type": paragraph_block.block_type,
                            "char_start": start,
                            "char_end": end,
                            "text_preview": paragraph_text[:160],
                            "current_step": "sentence_split",
                            **parser_block_stats,
                        },
                    )
                sentence_units, block_diagnostics = self._build_sentence_units_for_paragraph_with_diagnostics(
                    paragraph_text,
                    block_type=paragraph_block.block_type,
                    paragraph_metadata=paragraph.metadata,
                    refinement_state=claim_refinement_state,
                )
                if block_diagnostics["claim_refinement_attempts"] > 0:
                    parser_block_stats["fine_split_run_blocks"] += 1
                else:
                    parser_block_stats["fine_split_not_run_blocks"] += 1
                if block_diagnostics["claim_refinement_hits"] > 0:
                    parser_block_stats["fine_split_hit_blocks"] += 1
                if progress_callback is not None:
                    progress_callback(
                        "parser_block_units_ready",
                        {
                            "parser_run_id": parser_run.id,
                            "document_id": document.id,
                            "block_id": paragraph.id,
                            "block_index": paragraph_index,
                            "total_blocks": total_blocks,
                            "block_type": paragraph_block.block_type,
                            "sentence_unit_count": len(sentence_units),
                            "current_step": "sentence_units_ready",
                            **dict(block_diagnostics),
                            **parser_block_stats,
                        },
                    )
                paragraph = replace(paragraph, sentence_count=len(sentence_units))
                paragraphs.append(paragraph)

                paragraph_cursor = start
                block_sentence_count = 0
                for sentence_unit in sentence_units:
                    sentence_text = str(sentence_unit.get("text") or "").strip()
                    if not sentence_text:
                        continue
                    if "char_start_offset" in sentence_unit and "char_end_offset" in sentence_unit:
                        sentence_start = start + int(sentence_unit["char_start_offset"])
                        sentence_end = start + int(sentence_unit["char_end_offset"])
                    else:
                        sentence_start = raw_text.find(sentence_text, paragraph_cursor, end + 1)
                        if sentence_start < 0:
                            sentence_start = paragraph_cursor
                        sentence_end = sentence_start + len(sentence_text)
                    sentence_metadata = {
                        "paragraph_order": paragraph_index,
                        "block_type": paragraph_block.block_type,
                        "page_number": paragraph_block.page_number,
                        **dict(sentence_unit.get("metadata") or {}),
                    }
                    if paragraph_block.block_type != "heading" and current_header_text:
                        sentence_metadata.update(
                            {
                                "header_context_text": current_header_text,
                                "header_context_paragraph_id": current_header_paragraph_id,
                                "header_context_sentence_id": current_header_sentence_id,
                            }
                        )
                    sentence = Sentence(
                        tenant=source.tenant,
                        corpus_uuid=source.corpus_uuid,
                        source_id=source.id,
                        document_id=document.id,
                        paragraph_id=paragraph.id,
                        order_index=sentence_index,
                        text_content=sentence_text,
                        char_start=sentence_start,
                        char_end=sentence_end,
                        token_count=len([token for token in sentence_text.split() if token]),
                        metadata={
                            **sentence_metadata,
                            "language": detect_language(
                                sentence_text,
                                preferred_language=document.language or source.metadata.get("language") if isinstance(source.metadata, dict) else None,
                            ),
                        },
                    )
                    sentences.append(sentence)
                    if paragraph_block.block_type == "heading":
                        current_header_text = sentence_text
                        current_header_paragraph_id = paragraph.id
                        current_header_sentence_id = sentence.id
                    paragraph_cursor = sentence_end
                    sentence_index += 1
                    block_sentence_count += 1
                cursor = end
                parser_block_stats["blocks_completed"] += 1
                if progress_callback is not None:
                    progress_callback(
                        "parser_block_completed",
                        {
                            "parser_run_id": parser_run.id,
                            "document_id": document.id,
                            "block_id": paragraph.id,
                            "block_index": paragraph_index,
                            "total_blocks": total_blocks,
                            "block_type": paragraph_block.block_type,
                            "sentence_count": block_sentence_count,
                            "current_step": "sentence_records_built",
                            **dict(block_diagnostics),
                            **parser_block_stats,
                        },
                    )

            self._paragraph_store.create_many(paragraphs)
            created_sentences = self._sentence_store.create_many(sentences)
            if progress_callback is not None:
                progress_callback(
                    "parser_completed",
                    {
                        "parser_run_id": parser_run.id,
                        "document_id": document.id,
                        "paragraph_count": len(paragraphs),
                        "sentence_count": len(created_sentences),
                        **parser_block_stats,
                    },
                )
            interpretation_run = self._interpret_document(
                source=source,
                document=document,
                sentences=created_sentences,
                created_by=created_by,
                progress_callback=progress_callback,
            )
            self._source_store.update(replace(source, status="ingested", metadata={**source.metadata, "parser_status": "completed"}))
            finished_run = self._parser_run_store.update(
                replace(
                    parser_run,
                    status="completed",
                    parser_type=str(extracted_document.metadata.get("extraction_engine") or parser_run.parser_type),
                    language="hu",
                    completed_at=_utcnow(),
                    updated_at=_utcnow(),
                    metadata={
                        **parser_run.metadata,
                        "document_id": document.id,
                        "paragraph_count": len(paragraphs),
                        "sentence_count": len(created_sentences),
                        "interpretation_run_id": interpretation_run.id if interpretation_run is not None else None,
                        "parser_type": str(extracted_document.metadata.get("extraction_engine") or parser_run.parser_type),
                    },
                )
            )
            self._log_step(
                "parser.source.completed",
                status="ok",
                tenant=source.tenant,
                corpus_uuid=source.corpus_uuid,
                source_id=source.id,
                document_id=document.id,
                paragraph_count=len(paragraphs),
                sentence_count=len(created_sentences),
            )
            return finished_run
        except Exception as exc:
            failed_run = self._parser_run_store.update(
                replace(
                    parser_run,
                    status="failed",
                    error_message=self._truncate_error_message(
                        exc,
                        max_length=self._PARSER_ERROR_MESSAGE_MAX,
                    ),
                    completed_at=_utcnow(),
                    updated_at=_utcnow(),
                )
            )
            self._source_store.update(replace(source, status="failed", metadata={**source.metadata, "parser_status": "failed"}))
            if progress_callback is not None:
                progress_callback(
                    "parser_failed",
                    {"parser_run_id": parser_run.id, "error_message": failed_run.error_message},
                )
            self._log_step(
                "parser.source.failed",
                status="error",
                tenant=source.tenant,
                corpus_uuid=source.corpus_uuid,
                source_id=source.id,
                error=str(exc),
            )
            return failed_run

    def create_text_ingest_run(
        self,
        *,
        tenant: str,
        corpus_uuid: str,
        title: str,
        text: str,
        created_by: int | None,
    ) -> IngestRun:
        self._require_corpus(corpus_uuid)
        payload = _normalize_text_payload(text)
        if not payload.strip():
            raise ValueError("Text input is required")
        run = self._ingest_run_store.create(
            IngestRun(
                tenant=tenant,
                corpus_uuid=corpus_uuid,
                input_channel="text",
                status="queued",
                batch_size=1,
                queued_count=1,
                pipeline_route="source_parser",
                created_by=created_by,
                metadata={"input_types": ["text"]},
            )
        )
        self._record_ingest_event(
            run_id=run.id,
            event_type="ingest_run_created",
            status="ok",
            message="Szöveges ingest run létrehozva.",
            created_by=created_by,
            batch_size=1,
        )
        item = IngestItem(
            ingest_run_id=run.id,
            tenant=tenant,
            corpus_uuid=corpus_uuid,
            queue_order=1,
            input_type="text",
            display_name=self._ensure_title(title, fallback="Text input"),
            title=self._ensure_title(title, fallback="Text input"),
            origin="manual:text",
            status="queued",
            progress_message="Várakozik a háttérfeldolgozásra.",
            pipeline_route="source_parser",
            created_by=created_by,
            metadata={"char_count": len(payload), "text_preview": payload[:160], "text_encoding": "utf-8"},
        )
        ingest_input = IngestInput(
            ingest_item_id=item.id,
            tenant=tenant,
            input_type="text",
            text_content=payload,
            size_bytes=len(payload.encode("utf-8")),
            encoding="utf-8",
            metadata={"title": item.title},
        )
        self._ingest_item_store.create_many([item])
        self._ingest_input_store.create_many([ingest_input])
        self._record_ingest_event(
            run_id=run.id,
            item_id=item.id,
            event_type="item_received",
            status="ok",
            message="Szöveges input rögzítve.",
            created_by=created_by,
            input_type="text",
            title=item.title,
        )
        return self._refresh_ingest_run(run.id)

    def create_file_ingest_run(
        self,
        *,
        tenant: str,
        corpus_uuid: str,
        files: list[dict[str, Any]],
        created_by: int | None,
    ) -> IngestRun:
        self._require_corpus(corpus_uuid)
        if not files:
            raise ValueError("At least one file is required")
        run = self._ingest_run_store.create(
            IngestRun(
                tenant=tenant,
                corpus_uuid=corpus_uuid,
                input_channel="file",
                status="queued",
                batch_size=len(files),
                queued_count=len(files),
                pipeline_route="source_parser",
                created_by=created_by,
                metadata={"input_types": ["file"], "batch_size": len(files)},
            )
        )
        self._record_ingest_event(
            run_id=run.id,
            event_type="ingest_run_created",
            status="ok",
            message="Fájlos ingest run létrehozva.",
            created_by=created_by,
            batch_size=len(files),
        )
        try:
            items: list[IngestItem] = []
            inputs: list[IngestInput] = []
            for index, file_info in enumerate(files, start=1):
                filename = str(file_info.get("filename") or f"upload-{index}.bin")
                content = bytes(file_info.get("content") or b"")
                if not content:
                    raise ValueError(f"Empty file input: {filename}")
                item = IngestItem(
                    ingest_run_id=run.id,
                    tenant=tenant,
                    corpus_uuid=corpus_uuid,
                    queue_order=index,
                    input_type="file",
                    display_name=filename,
                    title=self._ensure_title(str(file_info.get("title") or filename), fallback=filename),
                    origin=filename,
                    status="queued",
                    progress_message="Fájl rögzítve, háttérben feldolgozásra vár.",
                    pipeline_route="source_parser",
                    created_by=created_by,
                    metadata={"filename": filename},
                )
                object_key = self._build_storage_key(tenant=tenant, run_id=run.id, item_id=item.id, filename=filename)
                stored = self._object_storage.put_bytes(
                    key=object_key,
                    content=content,
                    content_type=str(file_info.get("mime_type") or "application/octet-stream"),
                    metadata={"run_id": run.id, "item_id": item.id, "corpus_uuid": corpus_uuid},
                )
                items.append(item)
                inputs.append(
                    IngestInput(
                        ingest_item_id=item.id,
                        tenant=tenant,
                        input_type="file",
                        storage_provider=stored.provider,
                        bucket_name=stored.bucket,
                        object_key=stored.key,
                        original_filename=filename,
                        mime_type=str(file_info.get("mime_type") or stored.content_type or "application/octet-stream"),
                        size_bytes=stored.size_bytes or len(content),
                        checksum_sha256=self._sha256_bytes(content),
                        metadata={"etag": stored.etag},
                    )
                )
            created_items = self._ingest_item_store.create_many(items)
            self._ingest_input_store.create_many(inputs)
            for item in created_items:
                self._record_ingest_event(
                    run_id=run.id,
                    item_id=item.id,
                    event_type="stored_to_object_storage",
                    status="ok",
                    message="Fájl mentve object storage-ba.",
                    created_by=created_by,
                    display_name=item.display_name,
                )
            return self._refresh_ingest_run(run.id)
        except Exception as exc:
            failed_run = self._ingest_run_store.update(
                replace(
                    run,
                    status="failed",
                    failed_count=len(files),
                    queued_count=0,
                    processing_count=0,
                    updated_at=_utcnow(),
                    completed_at=_utcnow(),
                    metadata={**run.metadata, "error_message": str(exc)},
                )
            )
            self._record_ingest_event(
                run_id=run.id,
                event_type="storage_failed",
                status="failed",
                message=str(exc),
                created_by=created_by,
            )
            self._log_step(
                "ingest.file.create_failed",
                status="error",
                tenant=tenant,
                ingest_run_id=failed_run.id,
            )
            raise

    def create_url_ingest_run(
        self,
        *,
        tenant: str,
        corpus_uuid: str,
        urls: list[dict[str, Any]],
        created_by: int | None,
    ) -> IngestRun:
        self._require_corpus(corpus_uuid)
        normalized_urls = [item for item in urls if str(item.get("url") or "").strip()]
        if not normalized_urls:
            raise ValueError("At least one URL is required")
        run = self._ingest_run_store.create(
            IngestRun(
                tenant=tenant,
                corpus_uuid=corpus_uuid,
                input_channel="url",
                status="queued",
                batch_size=len(normalized_urls),
                queued_count=len(normalized_urls),
                pipeline_route="source_parser",
                created_by=created_by,
                metadata={"input_types": ["url"], "batch_size": len(normalized_urls)},
            )
        )
        self._record_ingest_event(
            run_id=run.id,
            event_type="ingest_run_created",
            status="ok",
            message="URL ingest run létrehozva.",
            created_by=created_by,
            batch_size=len(normalized_urls),
        )
        items: list[IngestItem] = []
        inputs: list[IngestInput] = []
        for index, url_info in enumerate(normalized_urls, start=1):
            url = str(url_info.get("url") or "").strip()
            display_name = str(url_info.get("title") or url)
            item = IngestItem(
                ingest_run_id=run.id,
                tenant=tenant,
                corpus_uuid=corpus_uuid,
                queue_order=index,
                input_type="url",
                display_name=display_name[:255],
                title=self._ensure_title(str(url_info.get("title") or display_name), fallback=url),
                origin=url,
                status="queued",
                progress_message="URL rögzítve, elérhetőség ellenőrzésre vár.",
                pipeline_route="source_parser",
                created_by=created_by,
                metadata={"url": url},
            )
            items.append(item)
            inputs.append(
                IngestInput(
                    ingest_item_id=item.id,
                    tenant=tenant,
                    input_type="url",
                    origin_url=url,
                    metadata={"title": item.title},
                )
            )
        self._ingest_item_store.create_many(items)
        self._ingest_input_store.create_many(inputs)
        for item in items:
            self._record_ingest_event(
                run_id=run.id,
                item_id=item.id,
                event_type="item_received",
                status="ok",
                message="URL input rögzítve.",
                created_by=created_by,
                origin=item.origin,
            )
        return self._refresh_ingest_run(run.id)

    def get_ingest_run(self, run_id: str) -> IngestRun | None:
        run = self._ingest_run_store.get(run_id)
        if run is None:
            return None
        if run.status in {"queued", "processing"}:
            return self._refresh_ingest_run(run_id)
        return run

    def list_ingest_runs(self, corpus_uuid: str, *, limit: int = 20) -> list[IngestRun]:
        runs = self._ingest_run_store.list_for_corpus(corpus_uuid, limit=limit)
        refreshed: list[IngestRun] = []
        for run in runs:
            if run.status in {"queued", "processing"}:
                refreshed.append(self._refresh_ingest_run(run.id))
            else:
                refreshed.append(run)
        return refreshed

    def get_ingest_item(self, item_id: str) -> IngestItem | None:
        return self._ingest_item_store.get(item_id)

    def get_ingest_input_for_item(self, item_id: str) -> IngestInput | None:
        return self._ingest_input_store.get_for_item(item_id)

    def get_document_for_ingest_item(self, item_id: str) -> Document | None:
        item = self._ingest_item_store.get(item_id)
        if item is None or not item.source_id:
            return None
        return self._document_store.get_for_source(item.source_id)

    def list_paragraphs_for_ingest_item(self, item_id: str) -> list[Paragraph]:
        document = self.get_document_for_ingest_item(item_id)
        if document is None:
            return []
        return self._paragraph_store.list_for_document(document.id)

    def list_sentences_for_ingest_item(self, item_id: str) -> list[Sentence]:
        document = self.get_document_for_ingest_item(item_id)
        if document is None:
            return []
        sentences = self._sentence_store.list_for_document(document.id)
        enriched_sentences: list[Sentence] = []
        for sentence in sentences:
            detail = self.get_sentence_interpretation(sentence.id)
            interpretation = detail["interpretation"] if detail is not None else None
            if interpretation is None:
                enriched_sentences.append(sentence)
                continue
            enriched_sentences.append(
                replace(
                    sentence,
                    metadata={
                        **sentence.metadata,
                        "information_value_score": interpretation.information_value_score,
                        "information_value_status": interpretation.information_value_status,
                        "information_value_reason": interpretation.information_value_reason,
                    },
                )
            )
        return enriched_sentences

    def get_sentence_interpretation(self, sentence_id: str) -> dict[str, Any] | None:
        sentence = self._sentence_store.get(sentence_id)
        if sentence is None:
            return None

        if (
            self._sentence_interpretation_store is None
            or self._mention_store is None
            or self._claim_store is None
            or self._space_time_frame_store is None
        ):
            return self._build_sentence_interpretation_payload(sentence)
        try:
            interpretation = self._sentence_interpretation_store.get_for_sentence(sentence_id)
        except ProgrammingError as exc:
            if self._is_missing_table_error(
                exc,
                "knowledge_interpretation_runs",
                "knowledge_sentence_interpretations",
                "knowledge_mentions",
                "knowledge_claims",
                "knowledge_space_time_frames",
            ):
                return self._build_sentence_interpretation_payload(sentence)
            raise
        if interpretation is None:
            document = self._document_store.get(sentence.document_id)
            source = self._source_store.get(sentence.source_id)
            if document is not None and source is not None:
                self._interpret_document(
                    source=source,
                    document=document,
                    sentences=self._sentence_store.list_for_document(document.id),
                )
                interpretation = self._sentence_interpretation_store.get_for_sentence(sentence_id)
        if interpretation is None:
            return self._build_sentence_interpretation_payload(sentence)
        return {
            "interpretation": interpretation,
            "mentions": self._mention_store.list_for_sentence(sentence_id),
            "claims": self._claim_store.list_for_sentence(sentence_id),
            "space_time_frames": self._space_time_frame_store.list_for_sentence(sentence_id),
        }

    def read_ingest_file_bytes(self, item_id: str) -> tuple[bytes, str | None, str | None]:
        ingest_input = self._ingest_input_store.get_for_item(item_id)
        if ingest_input is None:
            raise ValueError("Ingest input not found")
        if ingest_input.input_type != "file":
            raise ValueError("Ingest input is not a file")
        if not ingest_input.bucket_name or not ingest_input.object_key:
            raise ValueError("Object storage reference is missing")
        stored = self._object_storage.get_bytes(key=ingest_input.object_key, bucket=ingest_input.bucket_name)
        return stored.body, ingest_input.mime_type or stored.ref.content_type, ingest_input.original_filename

    def list_ingest_items(self, run_id: str) -> list[IngestItem]:
        return self._ingest_item_store.list_for_run(run_id)

    def list_ingest_events(self, run_id: str) -> list[IngestEvent]:
        return self._ingest_event_store.list_for_run(run_id)

    def _delete_ingest_item_outputs(self, item: IngestItem) -> None:
        source_id = str(item.source_id or item.metadata.get("source_id") or "").strip()
        if not source_id:
            return

        document = self._document_store.get_for_source(source_id)
        if document is not None:
            if self._space_time_frame_store is not None:
                self._delete_for_document_if_table_exists(
                    self._space_time_frame_store,
                    document.id,
                    table_name="knowledge_space_time_frames",
                )
            if self._claim_store is not None:
                self._delete_for_document_if_table_exists(
                    self._claim_store,
                    document.id,
                    table_name="knowledge_claims",
                )
            if self._mention_store is not None:
                self._delete_for_document_if_table_exists(
                    self._mention_store,
                    document.id,
                    table_name="knowledge_mentions",
                )
            if self._sentence_interpretation_store is not None:
                self._delete_for_document_if_table_exists(
                    self._sentence_interpretation_store,
                    document.id,
                    table_name="knowledge_sentence_interpretations",
                )
            if self._interpretation_run_store is not None:
                self._delete_for_document_if_table_exists(
                    self._interpretation_run_store,
                    document.id,
                    table_name="knowledge_interpretation_runs",
                )
            self._sentence_store.delete_for_document(document.id)
            self._paragraph_store.delete_for_document(document.id)
            self._document_store.delete_for_source(source_id)

        self._parser_run_store.delete_for_source(source_id)
        self._source_store.delete(source_id)

    @staticmethod
    def _reset_reprocess_item_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
        cleaned = dict(metadata)
        for key in (
            "source_id",
            "parser_run_id",
            "document_id",
            "sentence_count",
            "paragraph_count",
            "interpretation_run_id",
            "handoff_target",
        ):
            cleaned.pop(key, None)
        cleaned.pop("processing_summary", None)
        cleaned["reprocess_requested_at"] = _utcnow().isoformat()
        return cleaned

    def request_ingest_item_reprocess(self, item_id: str, *, current_user_id: int | None = None) -> IngestRun:
        item = self._ingest_item_store.get(item_id)
        if item is None:
            raise ValueError("Ingest item not found")
        run = self._ingest_run_store.get(item.ingest_run_id)
        if run is None:
            raise ValueError("Ingest run not found")
        if run.status in {"queued", "processing"}:
            run = self._refresh_ingest_run(run.id)
            item = self._ingest_item_store.get(item_id) or item
        source_id = str(item.source_id or item.metadata.get("source_id") or "").strip()
        stale_parser_processing = bool(source_id) and self._is_stale_parser_processing(source_id, updated_at=item.updated_at)
        if (run.status in {"queued", "processing"} or item.status == "processing") and not stale_parser_processing:
            raise ValueError("Az ingest rekord jelenleg feldolgozás alatt áll, ezért most nem indítható újra.")

        self._delete_ingest_item_outputs(item)
        reset_item = self._ingest_item_store.update(
            replace(
                item,
                status="received",
                progress_message="Újrafeldolgozás ütemezve.",
                result_message=None,
                error_code=None,
                error_message=None,
                duplicate_of_item_id=None,
                duplicate_of_source_id=None,
                parser_job_id=None,
                source_id=None,
                content_hash=None,
                started_at=None,
                completed_at=None,
                updated_at=_utcnow(),
                metadata=self._reset_reprocess_item_metadata(item.metadata),
            )
        )
        self._record_ingest_event(
            run_id=run.id,
            item_id=reset_item.id,
            event_type="reprocess_requested",
            status="ok",
            message="A korábbi forrás törölve lett, az ingest item újrafeldolgozásra vár.",
            created_by=current_user_id,
        )
        return self._refresh_ingest_run(run.id)

    def _process_single_ingest_item(
        self,
        *,
        started_run: IngestRun,
        item: IngestItem,
        ingest_input: IngestInput | None,
        force_reprocess: bool = False,
    ) -> bool:
        run_id = started_run.id
        if ingest_input is None:
            failed_item = self._ingest_item_store.update(
                replace(
                    item,
                    status="failed",
                    error_code="missing_input",
                    error_message="Nem található ingest input rekord.",
                    progress_message="Hiányzó input rekord.",
                    completed_at=_utcnow(),
                    updated_at=_utcnow(),
                )
            )
            failed_item = self._update_item_processing_summary(
                failed_item,
                module_updates={
                    "parser": self._build_processing_module(
                        key="parser",
                        status="failed",
                        label="Mondatkinyerés",
                        error_message=failed_item.error_message,
                    ),
                    "sentence_interpretation": self._build_processing_module(
                        key="sentence_interpretation",
                        status="failed",
                        label="Mondatértelmezés",
                        error_message=failed_item.error_message,
                    ),
                    "sentence_evaluation": self._build_processing_module(
                        key="sentence_evaluation",
                        status="failed",
                        label="Mondatértékelés",
                        error_message=failed_item.error_message,
                    ),
                },
            )
            self._record_ingest_event(
                run_id=run_id,
                item_id=item.id,
                event_type="validation_failed",
                status="failed",
                message=failed_item.error_message,
                error_code=failed_item.error_code,
            )
            return bool(started_run.continue_on_error)

        current_item = self._ingest_item_store.update(
            replace(
                item,
                status="processing",
                progress_message="Validáció és route-előkészítés folyamatban.",
                started_at=item.started_at or _utcnow(),
                completed_at=None,
                updated_at=_utcnow(),
            )
        )
        current_item = self._update_item_processing_summary(
            current_item,
            module_updates={
                "parser": self._build_processing_module(
                    key="parser",
                    status="queued",
                    label="Mondatkinyerés",
                    message="A parser modul még nem indult el.",
                ),
                "sentence_interpretation": self._build_processing_module(
                    key="sentence_interpretation",
                    status="queued",
                    label="Mondatértelmezés",
                    message="Az értelmező modul még nem indult el.",
                ),
                "sentence_evaluation": self._build_processing_module(
                    key="sentence_evaluation",
                    status="queued",
                    label="Mondatértékelés",
                    message="Az értékelő rész még nem indult el.",
                ),
            },
            document_progress=self._build_document_progress(
                phase="parser",
                processed_parts=0,
                total_parts=None,
                label="A dokumentum előkészítése még nem indult el.",
            ),
        )
        self._refresh_ingest_run(run_id)
        try:
            if ingest_input.input_type == "text":
                content_hash = self._sha256_text(_normalize_text_payload(ingest_input.text_content))
            elif ingest_input.input_type == "file":
                if not ingest_input.bucket_name or not ingest_input.object_key:
                    raise ValueError("Missing object storage reference for file input")
                content_hash = str(ingest_input.checksum_sha256 or "")
                if not content_hash:
                    stored = self._object_storage.get_bytes(
                        key=ingest_input.object_key,
                        bucket=ingest_input.bucket_name,
                    )
                    content_hash = self._sha256_bytes(stored.body)
            elif ingest_input.input_type == "url":
                if not ingest_input.origin_url:
                    raise ValueError("URL input is missing origin_url")
                response = requests.head(ingest_input.origin_url, allow_redirects=True, timeout=15)
                if response.status_code >= 400:
                    raise ValueError(f"URL is not reachable ({response.status_code})")
                content_hash = self._sha256_text(ingest_input.origin_url)
                current_item = self._ingest_item_store.update(
                    replace(
                        current_item,
                        progress_message=f"URL elérhető, válasz: {response.status_code}.",
                        updated_at=_utcnow(),
                        metadata={
                            **current_item.metadata,
                            "url_status_code": response.status_code,
                            "url_content_type": response.headers.get("content-type"),
                        },
                    )
                )
            else:
                raise ValueError(f"Unsupported ingest input type: {ingest_input.input_type}")

            duplicate = None
            if not force_reprocess:
                duplicate = self._ingest_item_store.find_by_hash(
                    corpus_uuid=current_item.corpus_uuid,
                    content_hash=content_hash,
                    exclude_item_id=current_item.id,
                )
            if duplicate is not None:
                finished_item = self._ingest_item_store.update(
                    replace(
                        current_item,
                        status="duplicate",
                        content_hash=content_hash,
                        duplicate_of_item_id=duplicate.id,
                        duplicate_of_source_id=duplicate.source_id,
                        result_message="Duplikátumként jelölve.",
                        progress_message="Duplikált input, parser nem indul.",
                        completed_at=_utcnow(),
                        updated_at=_utcnow(),
                    )
                )
                finished_item = self._update_item_processing_summary(
                    finished_item,
                    module_updates={
                        "parser": self._build_processing_module(
                            key="parser",
                            status="skipped",
                            label="Mondatkinyerés",
                            message="Duplikátum miatt nem indult parser.",
                        ),
                        "sentence_interpretation": self._build_processing_module(
                            key="sentence_interpretation",
                            status="skipped",
                            label="Mondatértelmezés",
                            message="Duplikátum miatt nem indult értelmezés.",
                        ),
                        "sentence_evaluation": self._build_processing_module(
                            key="sentence_evaluation",
                            status="skipped",
                            label="Mondatértékelés",
                            message="Duplikátum miatt nem indult értékelés.",
                        ),
                    },
                    document_progress=self._build_document_progress(
                        phase="duplicate",
                        processed_parts=0,
                        total_parts=0,
                        label="Duplikátumként jelölve, nincs további feldolgozás.",
                    ),
                )
                self._record_ingest_event(
                    run_id=run_id,
                    item_id=current_item.id,
                    event_type="duplicate_detected",
                    status="ok",
                    message="Duplikált input felismerve.",
                    duplicate_of_item_id=duplicate.id,
                    content_hash=content_hash,
                )
            else:
                created_source = self._create_source_from_ingest_item(
                    tenant=started_run.tenant,
                    item=current_item,
                    ingest_input=ingest_input,
                    content_hash=content_hash,
                    created_by=current_item.created_by,
                )
                finished_item = self._ingest_item_store.update(
                    replace(
                        current_item,
                        status="processing",
                        content_hash=content_hash,
                        progress_message="Ingest lezárva, parserre vár.",
                        result_message="Sikeresen előkészítve a parser modulhoz.",
                        source_id=created_source.id,
                        completed_at=None,
                        updated_at=_utcnow(),
                        metadata={**current_item.metadata, "handoff_target": "source_parser", "source_id": created_source.id},
                    )
                )
                self._record_ingest_event(
                    run_id=run_id,
                    item_id=current_item.id,
                    event_type="source_created",
                    status="ok",
                    message="Source rekord létrehozva az ingest inputhoz.",
                    source_id=created_source.id,
                    source_type=created_source.source_type,
                )
                self._record_ingest_event(
                    run_id=run_id,
                    item_id=current_item.id,
                    event_type="parser_handover_ready",
                    status="ok",
                    message="Az input készen áll a parser modul számára.",
                    content_hash=content_hash,
                )
                finished_item = self._update_item_processing_summary(
                    finished_item,
                    progress_message="A parser modul megkezdte a dokumentum előkészítését.",
                    module_updates={
                        "parser": self._build_processing_module(
                            key="parser",
                            status="processing",
                            label="Mondatkinyerés",
                            message="A parser modul feldolgozza a dokumentumot.",
                        ),
                    },
                    extra_metadata={"source_id": created_source.id},
                )

                def _pipeline_progress(stage: str, payload: dict[str, Any]) -> None:
                    nonlocal finished_item
                    if stage == "parser_started":
                        finished_item = self._update_item_processing_summary(
                            finished_item,
                            progress_message="A parser modul fut, a dokumentum szerkezetét készíti elő.",
                            module_updates={
                                "parser": self._build_processing_module(
                                    key="parser",
                                    status="processing",
                                    label="Mondatkinyerés",
                                    run_id=str(payload.get("parser_run_id") or ""),
                                    message="A parser modul fut.",
                                ),
                            },
                        )
                        return
                    if stage in {"parser_block_started", "parser_block_units_ready", "parser_block_completed"}:
                        block_index = int(payload.get("block_index") or 0)
                        total_blocks = int(payload.get("total_blocks") or 0)
                        block_id = str(payload.get("block_id") or "")
                        block_type = str(payload.get("block_type") or "") or "unknown"
                        current_step = str(payload.get("current_step") or "") or "parser"
                        fine_split_run_blocks = int(payload.get("fine_split_run_blocks") or 0)
                        fine_split_not_run_blocks = int(payload.get("fine_split_not_run_blocks") or 0)
                        parser_message = (
                            f"Blokk {block_index} / {total_blocks} ({block_type}) | "
                            f"ID: {block_id} | lépés: {current_step}"
                        )
                        progress_message = parser_message
                        if stage == "parser_block_units_ready":
                            progress_message = (
                                f"{parser_message} | mondatjelöltek: {int(payload.get('candidate_count') or 0)} | "
                                f"finomvágás futott: {int(payload.get('claim_refinement_attempts') or 0)} jelölten | "
                                f"finomított egységek: {int(payload.get('claim_refinement_units') or 0)}"
                            )
                        elif stage == "parser_block_completed":
                            progress_message = (
                                f"{parser_message} | blokk mondatok: {int(payload.get('sentence_count') or 0)} | "
                                f"finomvágás blokkok: {fine_split_run_blocks} igen / {fine_split_not_run_blocks} nem"
                            )
                        finished_item = self._update_item_processing_summary(
                            finished_item,
                            progress_message=progress_message,
                            module_updates={
                                "parser": self._build_processing_module(
                                    key="parser",
                                    status="processing",
                                    label="Mondatkinyerés",
                                    processed_parts=int(payload.get("blocks_completed") or 0),
                                    total_parts=total_blocks,
                                    run_id=str(payload.get("parser_run_id") or ""),
                                    message=progress_message,
                                ),
                            },
                            document_progress=self._build_document_progress(
                                phase="parser",
                                processed_parts=int(payload.get("blocks_completed") or 0),
                                total_parts=total_blocks,
                                label=progress_message,
                            ),
                            extra_metadata={
                                "parser_block_status": {
                                    "block_id": block_id or None,
                                    "block_index": block_index,
                                    "total_blocks": total_blocks,
                                    "block_type": block_type,
                                    "current_step": current_step,
                                    "sentence_count": int(payload.get("sentence_count") or 0),
                                    "sentence_unit_count": int(payload.get("sentence_unit_count") or 0),
                                    "candidate_count": int(payload.get("candidate_count") or 0),
                                    "strong_candidate_count": int(payload.get("strong_candidate_count") or 0),
                                    "weak_candidate_count": int(payload.get("weak_candidate_count") or 0),
                                    "claim_refinement_attempts": int(payload.get("claim_refinement_attempts") or 0),
                                    "claim_refinement_hits": int(payload.get("claim_refinement_hits") or 0),
                                    "claim_refinement_units": int(payload.get("claim_refinement_units") or 0),
                                    "fallback_used": bool(payload.get("fallback_used") or False),
                                },
                                "parser_block_counters": {
                                    "blocks_started": int(payload.get("blocks_started") or 0),
                                    "blocks_completed": int(payload.get("blocks_completed") or 0),
                                    "total_blocks": total_blocks,
                                    "fine_split_run_blocks": fine_split_run_blocks,
                                    "fine_split_not_run_blocks": fine_split_not_run_blocks,
                                },
                            },
                        )
                        return
                    if stage == "parser_completed":
                        sentence_count = int(payload.get("sentence_count") or 0)
                        finished_item = self._update_item_processing_summary(
                            finished_item,
                            progress_message=f"A parser elkészült, {sentence_count} mondat azonosítva.",
                            module_updates={
                                "parser": self._build_processing_module(
                                    key="parser",
                                    status="completed",
                                    label="Mondatkinyerés",
                                    processed_parts=sentence_count,
                                    total_parts=sentence_count,
                                    run_id=str(payload.get("parser_run_id") or ""),
                                    message="A parser modul elkészült.",
                                ),
                                "sentence_interpretation": self._build_processing_module(
                                    key="sentence_interpretation",
                                    status="queued",
                                    label="Mondatértelmezés",
                                    processed_parts=0,
                                    total_parts=sentence_count,
                                    message="A mondatok értelmezése indulásra kész.",
                                ),
                                "sentence_evaluation": self._build_processing_module(
                                    key="sentence_evaluation",
                                    status="queued",
                                    label="Mondatértékelés",
                                    processed_parts=0,
                                    total_parts=sentence_count,
                                    message="A mondatok értékelése indulásra kész.",
                                ),
                            },
                            document_progress=self._build_document_progress(
                                phase="sentence_interpretation",
                                processed_parts=0,
                                total_parts=sentence_count,
                                label=f"0 / {sentence_count} mondat értelmezve",
                            ),
                            extra_metadata={
                                "parser_run_id": payload.get("parser_run_id"),
                                "document_id": payload.get("document_id"),
                                "sentence_count": sentence_count,
                                "paragraph_count": int(payload.get("paragraph_count") or 0),
                                "parser_block_counters": {
                                    "blocks_started": int(payload.get("blocks_started") or 0),
                                    "blocks_completed": int(payload.get("blocks_completed") or 0),
                                    "total_blocks": int(payload.get("total_blocks") or 0),
                                    "fine_split_run_blocks": int(payload.get("fine_split_run_blocks") or 0),
                                    "fine_split_not_run_blocks": int(payload.get("fine_split_not_run_blocks") or 0),
                                },
                            },
                        )
                        return
                    if stage == "parser_failed":
                        finished_item = self._update_item_processing_summary(
                            finished_item,
                            progress_message="A parser modul hibára futott.",
                            module_updates={
                                "parser": self._build_processing_module(
                                    key="parser",
                                    status="failed",
                                    label="Mondatkinyerés",
                                    run_id=str(payload.get("parser_run_id") or ""),
                                    error_message=str(payload.get("error_message") or ""),
                                ),
                            },
                        )
                        return
                    if stage == "interpretation_started":
                        total_sentences = int(payload.get("total_sentences") or 0)
                        finished_item = self._update_item_processing_summary(
                            finished_item,
                            progress_message="A mondatok értelmezése és értékelése folyamatban van.",
                            module_updates={
                                "sentence_interpretation": self._build_processing_module(
                                    key="sentence_interpretation",
                                    status="processing",
                                    label="Mondatértelmezés",
                                    processed_parts=int(payload.get("processed_sentences") or 0),
                                    total_parts=total_sentences,
                                    run_id=str(payload.get("interpretation_run_id") or ""),
                                    message="A mondatok értelmezése folyamatban van.",
                                ),
                                "sentence_evaluation": self._build_processing_module(
                                    key="sentence_evaluation",
                                    status="processing",
                                    label="Mondatértékelés",
                                    processed_parts=int(payload.get("processed_sentences") or 0),
                                    total_parts=total_sentences,
                                    message="A mondatok információértékének meghatározása folyamatban van.",
                                ),
                            },
                            document_progress=self._build_document_progress(
                                phase="sentence_interpretation",
                                processed_parts=int(payload.get("processed_sentences") or 0),
                                total_parts=total_sentences,
                                label=f"0 / {total_sentences} mondat kész",
                            ),
                            extra_metadata={"interpretation_run_id": payload.get("interpretation_run_id")},
                        )
                        return
                    if stage == "interpretation_progress":
                        processed_sentences = int(payload.get("processed_sentences") or 0)
                        total_sentences = int(payload.get("total_sentences") or 0)
                        finished_item = self._update_item_processing_summary(
                            finished_item,
                            progress_message=f"Mondatfeldolgozás: {processed_sentences} / {total_sentences} kész.",
                            module_updates={
                                "sentence_interpretation": self._build_processing_module(
                                    key="sentence_interpretation",
                                    status="processing",
                                    label="Mondatértelmezés",
                                    processed_parts=processed_sentences,
                                    total_parts=total_sentences,
                                    run_id=str(payload.get("interpretation_run_id") or ""),
                                    message=f"{processed_sentences} / {total_sentences} mondat értelmezve.",
                                ),
                                "sentence_evaluation": self._build_processing_module(
                                    key="sentence_evaluation",
                                    status="processing",
                                    label="Mondatértékelés",
                                    processed_parts=processed_sentences,
                                    total_parts=total_sentences,
                                    message=f"{processed_sentences} / {total_sentences} mondat értékelve.",
                                ),
                            },
                            document_progress=self._build_document_progress(
                                phase="sentence_interpretation",
                                processed_parts=processed_sentences,
                                total_parts=total_sentences,
                                label=f"{processed_sentences} / {total_sentences} mondat kész",
                            ),
                        )
                        return
                    if stage == "interpretation_completed":
                        processed_sentences = int(payload.get("processed_sentences") or 0)
                        total_sentences = int(payload.get("total_sentences") or processed_sentences)
                        quality = dict(payload.get("quality") or {})
                        finished_item = self._update_item_processing_summary(
                            finished_item,
                            progress_message=f"A mondatok értelmezése elkészült ({processed_sentences} / {total_sentences}).",
                            module_updates={
                                "sentence_interpretation": self._build_processing_module(
                                    key="sentence_interpretation",
                                    status="completed",
                                    label="Mondatértelmezés",
                                    processed_parts=processed_sentences,
                                    total_parts=total_sentences,
                                    run_id=str(payload.get("interpretation_run_id") or ""),
                                    message="A mondatok értelmezése elkészült.",
                                ),
                                "sentence_evaluation": self._build_processing_module(
                                    key="sentence_evaluation",
                                    status="completed",
                                    label="Mondatértékelés",
                                    processed_parts=processed_sentences,
                                    total_parts=total_sentences,
                                    message="A mondatok információérték-értékelése elkészült.",
                                ),
                            },
                            document_progress=self._build_document_progress(
                                phase="sentence_interpretation",
                                processed_parts=processed_sentences,
                                total_parts=total_sentences,
                                label=f"{processed_sentences} / {total_sentences} mondat kész",
                            ),
                            extra_metadata={"interpretation_quality": quality},
                        )
                        return
                    if stage == "interpretation_failed":
                        finished_item = self._update_item_processing_summary(
                            finished_item,
                            progress_message="A mondatértelmezés hibára futott.",
                            module_updates={
                                "sentence_interpretation": self._build_processing_module(
                                    key="sentence_interpretation",
                                    status="failed",
                                    label="Mondatértelmezés",
                                    processed_parts=int(payload.get("processed_sentences") or 0),
                                    total_parts=int(payload.get("total_sentences") or 0),
                                    run_id=str(payload.get("interpretation_run_id") or ""),
                                    error_message=str(payload.get("error_message") or ""),
                                ),
                                "sentence_evaluation": self._build_processing_module(
                                    key="sentence_evaluation",
                                    status="failed",
                                    label="Mondatértékelés",
                                    processed_parts=int(payload.get("processed_sentences") or 0),
                                    total_parts=int(payload.get("total_sentences") or 0),
                                    error_message=str(payload.get("error_message") or ""),
                                ),
                            },
                        )
                        return
                    if stage == "interpretation_skipped":
                        total_sentences = int(payload.get("total_sentences") or 0)
                        finished_item = self._update_item_processing_summary(
                            finished_item,
                            progress_message="A mondatértelmezés ebben a környezetben ki lett hagyva.",
                            module_updates={
                                "sentence_interpretation": self._build_processing_module(
                                    key="sentence_interpretation",
                                    status="skipped",
                                    label="Mondatértelmezés",
                                    processed_parts=0,
                                    total_parts=total_sentences,
                                    message=str(payload.get("reason") or "A modul nem elérhető."),
                                ),
                                "sentence_evaluation": self._build_processing_module(
                                    key="sentence_evaluation",
                                    status="skipped",
                                    label="Mondatértékelés",
                                    processed_parts=0,
                                    total_parts=total_sentences,
                                    message=str(payload.get("reason") or "A modul nem elérhető."),
                                ),
                            },
                            document_progress=self._build_document_progress(
                                phase="parser",
                                processed_parts=total_sentences,
                                total_parts=total_sentences,
                                label="A parser elkészült, az értelmezés ki lett hagyva.",
                            ),
                        )

                parser_run = self.parse_source(
                    created_source.id,
                    created_by=current_item.created_by,
                    progress_callback=_pipeline_progress,
                )
                parsed_document = self._document_store.get_for_source(created_source.id)
                sentence_count = 0
                if parsed_document is not None:
                    sentence_count = len(self._sentence_store.list_for_document(parsed_document.id))
                finished_item = self._update_item_processing_summary(
                    finished_item,
                    progress_message="A dokumentum feldolgozása sikeresen befejeződött.",
                    module_updates={
                        "parser": self._build_processing_module(
                            key="parser",
                            status="completed",
                            label="Mondatkinyerés",
                            processed_parts=sentence_count,
                            total_parts=sentence_count,
                            run_id=parser_run.id,
                            message="A parser modul elkészült.",
                        )
                    },
                    document_progress=self._build_document_progress(
                        phase="completed",
                        processed_parts=sentence_count,
                        total_parts=sentence_count,
                        label="A feldolgozás minden lépése elkészült.",
                    ),
                    extra_metadata={
                        "parser_run_id": parser_run.id,
                        "document_id": parsed_document.id if parsed_document is not None else None,
                        "sentence_count": sentence_count,
                    },
                )
                finished_item = self._ingest_item_store.update(
                    replace(
                        finished_item,
                        status="completed",
                        completed_at=_utcnow(),
                        updated_at=_utcnow(),
                    )
                )
            self._record_ingest_event(
                run_id=run_id,
                item_id=current_item.id,
                event_type="validation_passed",
                status="ok",
                message="Az input validációja sikeres.",
                content_hash=content_hash,
                force_reprocess=force_reprocess,
            )
            self._metrics_store.increment("ingest_item_success_count", 1)
            self._log_step(
                "ingest.item.complete",
                status="ok",
                tenant=started_run.tenant,
                ingest_run_id=run_id,
                ingest_item_id=finished_item.id,
            )
            return True
        except Exception as exc:
            safe_error_message = self._truncate_error_message(
                exc,
                max_length=self._PARSER_ERROR_MESSAGE_MAX,
            )
            failed_item = self._ingest_item_store.update(
                replace(
                    current_item,
                    status="failed",
                    error_code="processing_failed",
                    error_message=safe_error_message,
                    progress_message="Ingest feldolgozás közben hiba történt.",
                    completed_at=_utcnow(),
                    updated_at=_utcnow(),
                )
            )
            failed_item = self._update_item_processing_summary(
                failed_item,
                module_updates={
                    "parser": self._build_processing_module(
                        key="parser",
                        status="failed",
                        label="Mondatkinyerés",
                        error_message=safe_error_message,
                    ),
                    "sentence_interpretation": self._build_processing_module(
                        key="sentence_interpretation",
                        status="failed",
                        label="Mondatértelmezés",
                        error_message=safe_error_message,
                    ),
                    "sentence_evaluation": self._build_processing_module(
                        key="sentence_evaluation",
                        status="failed",
                        label="Mondatértékelés",
                        error_message=safe_error_message,
                    ),
                },
            )
            self._record_ingest_event(
                run_id=run_id,
                item_id=current_item.id,
                event_type="item_failed",
                status="failed",
                message=safe_error_message,
                force_reprocess=force_reprocess,
            )
            self._metrics_store.increment("ingest_item_failed_count", 1)
            self._log_step(
                "ingest.item.failed",
                status="error",
                tenant=started_run.tenant,
                ingest_run_id=run_id,
                ingest_item_id=failed_item.id,
            )
            return bool(started_run.continue_on_error)

    def process_ingest_run(self, run_id: str) -> IngestRun:
        run = self._ingest_run_store.get(run_id)
        if run is None:
            raise ValueError("Ingest run not found")
        started_run = self._ingest_run_store.update(
            replace(run, status="processing", started_at=run.started_at or _utcnow(), completed_at=None, updated_at=_utcnow())
        )
        items = self._ingest_item_store.list_for_run(run_id)
        with observability_scope(ingest_run_id=run_id, corpus_uuid=started_run.corpus_uuid):
            for item in items:
                try:
                    if not self._process_single_ingest_item(
                        started_run=started_run,
                        item=item,
                        ingest_input=self._ingest_input_store.get_for_item(item.id),
                    ):
                        break
                finally:
                    started_run = self._refresh_ingest_run(run_id)
        final_run = self._refresh_ingest_run(run_id)
        self._auto_refresh_semantic_block_index_after_ingest(final_run)
        final_run = self._refresh_ingest_run(run_id)
        self._log_ingest_trace_summary(run_id)
        return final_run

    def process_ingest_item(self, item_id: str) -> IngestRun:
        item = self._ingest_item_store.get(item_id)
        if item is None:
            raise ValueError("Ingest item not found")
        run = self._ingest_run_store.get(item.ingest_run_id)
        if run is None:
            raise ValueError("Ingest run not found")
        started_run = self._ingest_run_store.update(
            replace(run, status="processing", started_at=run.started_at or _utcnow(), completed_at=None, updated_at=_utcnow())
        )
        with observability_scope(ingest_run_id=run.id, ingest_item_id=item.id, corpus_uuid=run.corpus_uuid):
            try:
                self._process_single_ingest_item(
                    started_run=started_run,
                    item=item,
                    ingest_input=self._ingest_input_store.get_for_item(item.id),
                    force_reprocess=True,
                )
            finally:
                self._refresh_ingest_run(run.id)
        final_run = self._refresh_ingest_run(run.id)
        self._auto_refresh_semantic_block_index_after_ingest(final_run)
        final_run = self._refresh_ingest_run(run.id)
        self._log_ingest_trace_summary(run.id)
        return final_run

    def _auto_refresh_semantic_block_index_after_ingest(self, run: IngestRun) -> None:
        if run.status not in {"completed", "partial_success"}:
            return
        semantic_blocks = self._load_existing_semantic_blocks(corpus_uuid=run.corpus_uuid, exclude_interpretation_run_id=None)
        if not semantic_blocks:
            return
        metadata = dict(run.metadata or {})
        if metadata.get("semantic_block_auto_index_status") in {"completed", "scheduled"}:
            return
        try:
            build = self.schedule_index_build(
                tenant=run.tenant,
                corpus_uuid=run.corpus_uuid,
                index_profile_key=DEFAULT_INDEX_PROFILE.key,
                created_by=run.created_by,
            )
            metadata.update(
                {
                    "semantic_block_auto_index_status": "scheduled",
                    "semantic_block_auto_index_build_id": build.id,
                }
            )
            self._ingest_run_store.update(replace(run, metadata=metadata, updated_at=_utcnow()))

            async def _run() -> None:
                finished = await self.run_index_build(build.id)
                latest = self._ingest_run_store.get(run.id)
                if latest is not None:
                    latest_metadata = dict(latest.metadata or {})
                    latest_metadata.update(
                        {
                            "semantic_block_auto_index_status": finished.status,
                            "semantic_block_auto_index_build_id": finished.id,
                        }
                    )
                    self._ingest_run_store.update(replace(latest, metadata=latest_metadata, updated_at=_utcnow()))

            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                asyncio.run(_run())
            else:
                loop.create_task(_run())
        except Exception as exc:
            logger.warning("semantic block auto index refresh failed: %s", exc, exc_info=True)
            latest = self._ingest_run_store.get(run.id)
            if latest is not None:
                latest_metadata = dict(latest.metadata or {})
                latest_metadata.update(
                    {
                        "semantic_block_auto_index_status": "failed",
                        "semantic_block_auto_index_error": str(exc),
                    }
                )
                self._ingest_run_store.update(replace(latest, metadata=latest_metadata, updated_at=_utcnow()))

    def update_semantic_block_status(
        self,
        *,
        corpus_uuid: str,
        block_id: str,
        status: str,
        updated_by: int | None = None,
    ) -> dict[str, Any]:
        allowed = {"draft", "approved", "rejected", "withdrawn", "outdated", "disputed"}
        normalized_status = str(status or "").strip().lower()
        if normalized_status not in allowed:
            raise ValueError(f"Invalid semantic block status: {status}")
        if self._interpretation_run_store is None:
            raise ValueError("Interpretation run store is not available")
        list_for_corpus = getattr(self._interpretation_run_store, "list_for_corpus", None)
        if not callable(list_for_corpus):
            raise ValueError("Interpretation run listing is not available")
        runs = list_for_corpus(corpus_uuid, limit=50)
        for run in runs:
            metadata = dict(run.metadata or {})
            blocks = list(metadata.get("semantic_blocks") or [])
            changed = False
            updated_block: dict[str, Any] | None = None
            next_blocks: list[dict[str, Any]] = []
            for block in blocks:
                if not isinstance(block, dict):
                    next_blocks.append(block)
                    continue
                if str(block.get("id") or "") != str(block_id):
                    next_blocks.append(block)
                    continue
                updated_block = dict(block)
                block_metadata = dict(updated_block.get("metadata") or {})
                block_metadata["block_status"] = normalized_status
                block_metadata["status_updated_by"] = updated_by
                block_metadata["status_updated_at"] = _utcnow().isoformat()
                updated_block["metadata"] = block_metadata
                updated_block["block_status"] = normalized_status
                changed = True
                next_blocks.append(updated_block)
            if not changed:
                continue
            refreshed_blocks = enrich_semantic_blocks_with_quality(
                [dict(item) for item in next_blocks if isinstance(item, dict)],
                existing_blocks=[],
                source_type=None,
            )
            refreshed_by_id = {str(item.get("id") or ""): item for item in refreshed_blocks}
            metadata["semantic_blocks"] = [refreshed_by_id.get(str(item.get("id") or ""), item) if isinstance(item, dict) else item for item in next_blocks]
            self._interpretation_run_store.update(replace(run, metadata=metadata, updated_at=_utcnow()))
            return {
                "block_id": block_id,
                "status": normalized_status,
                "interpretation_run_id": run.id,
                "block": refreshed_by_id.get(str(block_id), updated_block or {}),
            }
        raise ValueError(f"Semantic block not found: {block_id}")

    def schedule_index_build(self, *, tenant: str, corpus_uuid: str, index_profile_key: str, created_by: int | None) -> IndexBuild:
        profile = self._default_index_profile(index_profile_key)
        corpus = self._corpus_store.get_by_uuid(corpus_uuid)
        if not corpus:
            raise ValueError("Corpus not found")
        collection_name = f"{getattr(corpus, 'qdrant_collection_name')}__{profile.key}"
        build = IndexBuild(
            tenant=tenant,
            corpus_uuid=corpus_uuid,
            index_profile_key=profile.key,
            collection_name=collection_name,
            created_by=created_by,
            metadata={"source_count": len(self._source_store.list_for_corpus(corpus_uuid))},
        )
        self._metrics_store.increment("build_count", 1)
        self._log_step("build.start", status="pending", tenant=tenant, build_id=build.id, corpus_uuid=corpus_uuid, profile=profile.key)
        return self._index_build_store.create(build)

    def get_index_build(self, build_id: str) -> IndexBuild | None:
        return self._index_build_store.get(build_id)

    async def run_index_build(self, build_id: str) -> IndexBuild:
        build = self._index_build_store.get(build_id)
        if build is None:
            raise ValueError("Index build not found")
        started = replace(build, status="building", started_at=_utcnow(), error=None)
        self._index_build_store.update(started)
        timer = time.perf_counter()
        try:
            sources = self._source_store.list_for_corpus(started.corpus_uuid)
            vector_index = self._vector_index_factory()
            profile = self._default_index_profile(started.index_profile_key)
            await vector_index.ensure_collection_schema_async(started.collection_name)

            total_chunks = 0
            for source in sources:
                text = str(source.raw_content or "").strip()
                if not text:
                    continue
                chunks = self._chunk_builder.build_chunks(text)
                total_chunks += len(chunks)
                rows = build_sentence_rows(chunks, source.title)
                for row in rows:
                    payload = row.setdefault("payload", {})
                    payload["source_id"] = source.id
                    payload["source_title"] = source.title
                    payload["build_id"] = started.id
                    payload["index_profile_key"] = profile.key
                await vector_index.upsert_sentence_points(started.collection_name, rows)
                self._source_store.update(replace(source, status="ingested"))

            retrieval_chunks = self._load_existing_retrieval_chunks(
                corpus_uuid=started.corpus_uuid,
                exclude_interpretation_run_id=None,
            )
            retrieval_chunk_rows = build_retrieval_chunk_index_rows(
                retrieval_chunks,
                build_id=started.id,
                index_profile_key=profile.key,
            )
            upsert_retrieval_chunks = getattr(vector_index, "upsert_retrieval_chunk_points", None)
            if callable(upsert_retrieval_chunks) and retrieval_chunk_rows:
                await upsert_retrieval_chunks(started.collection_name, retrieval_chunk_rows)

            semantic_blocks = self._load_existing_semantic_blocks(
                corpus_uuid=started.corpus_uuid,
                exclude_interpretation_run_id=None,
            )
            semantic_block_rows = build_semantic_block_index_rows(
                semantic_blocks,
                build_id=started.id,
                index_profile_key=profile.key,
            )
            upsert_semantic_blocks = getattr(vector_index, "upsert_semantic_block_points", None)
            if callable(upsert_semantic_blocks) and semantic_block_rows:
                await upsert_semantic_blocks(started.collection_name, semantic_block_rows)

            finished = replace(
                started,
                status="ready",
                chunk_count=total_chunks,
                completed_at=_utcnow(),
                metadata={
                    **started.metadata,
                    "source_count": len(sources),
                    "profile_key": profile.key,
                    "retrieval_chunk_count": len(retrieval_chunk_rows),
                    "retrieval_chunk_indexed": bool(retrieval_chunk_rows),
                    "semantic_block_count": len(semantic_block_rows),
                    "semantic_block_indexed": bool(semantic_block_rows),
                },
            )
            self._index_build_store.update(finished)
            self._metrics_store.increment("build_success_count", 1)
            self._metrics_store.increment("chunk_count", total_chunks)
            self._metrics_store.record_timing("build_duration_ms", (time.perf_counter() - timer) * 1000.0)
            self._log_step(
                "build.ready",
                status="ok",
                tenant=finished.tenant,
                build_id=finished.id,
                duration_ms=(time.perf_counter() - timer) * 1000.0,
                chunk_count=total_chunks,
                source_count=len(sources),
            )
            return finished
        except Exception as exc:
            failed = replace(started, status="failed", error=str(exc), completed_at=_utcnow())
            self._index_build_store.update(failed)
            self._metrics_store.increment("build_failed_count", 1)
            self._log_step("build.failed", status="error", tenant=failed.tenant, build_id=failed.id, error=str(exc))
            raise

    def _resolve_builds(self, *, corpus_uuid: str, build_ids: list[str] | None = None) -> list[IndexBuild]:
        if build_ids:
            builds = [item for item in (self._index_build_store.get(build_id) for build_id in build_ids) if item is not None]
        else:
            builds = [item for item in self._index_build_store.list_for_corpus(corpus_uuid) if item.status == "ready"]
            builds = builds[:1]
        return [item for item in builds if item.status == "ready"]

    async def _retrieve_hits_with_resilience(
        self,
        *,
        tenant: str,
        corpus_uuid: str,
        query: str,
        builds: list[IndexBuild],
        retrieval_profile: RetrievalProfile,
        query_profile: dict[str, Any],
    ) -> list[dict[str, Any]]:
        last_error: BaseException | None = None
        for attempt in range(1, _RETRIEVAL_RETRY_ATTEMPTS + 1):
            started = time.perf_counter()
            try:
                hits = await asyncio.wait_for(
                    self._retrieval_engine.retrieve(
                        query=query,
                        builds=builds,
                        retrieval_profile=retrieval_profile,
                        query_profile=query_profile,
                    ),
                    timeout=_RETRIEVAL_TIMEOUT_SECONDS,
                )
                self._metrics_store.record_timing("query_retrieval_duration_ms", (time.perf_counter() - started) * 1000.0)
                observe_platform_metric("knowledge.query.retrieval.duration_ms", (time.perf_counter() - started) * 1000.0, unit="ms")
                return hits
            except (TimeoutError, asyncio.TimeoutError) as exc:
                last_error = exc
                self._metrics_store.increment("query_retrieval_timeout_count", 1)
                increment_platform_metric("knowledge.query.retrieval.timeout.count", 1.0)
                log_structured_event(
                    "apps.knowledge",
                    "knowledge.query.retrieval_timeout",
                    level=logging.WARNING,
                    tenant=tenant,
                    corpus_uuid=corpus_uuid,
                    retry_count=attempt,
                    timeout_sec=_RETRIEVAL_TIMEOUT_SECONDS,
                )
            except Exception as exc:
                last_error = exc
                self._metrics_store.increment("query_retrieval_error_count", 1)
                increment_platform_metric("knowledge.query.retrieval.error.count", 1.0)
                log_structured_event(
                    "apps.knowledge",
                    "knowledge.query.retrieval_error",
                    level=logging.WARNING,
                    tenant=tenant,
                    corpus_uuid=corpus_uuid,
                    retry_count=attempt,
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                )
            if attempt < _RETRIEVAL_RETRY_ATTEMPTS:
                await asyncio.sleep(_RETRIEVAL_RETRY_BACKOFF_SECONDS * attempt)
        self._metrics_store.increment("query_retrieval_fallback_count", 1)
        increment_platform_metric("knowledge.query.retrieval.fallback.count", 1.0)
        if last_error is not None:
            log_structured_event(
                "apps.knowledge",
                "knowledge.query.retrieval_profile_fallback",
                level=logging.WARNING,
                tenant=tenant,
                corpus_uuid=corpus_uuid,
                error_type=type(last_error).__name__,
                error_message=str(last_error),
            )
        return []

    @staticmethod
    def _feedback_key(value: Any) -> str:
        text = str(value or "").strip()
        return canonicalize_entity_key(text) or fold_text(text)

    @staticmethod
    def _feedback_claim_text(claim: dict[str, Any]) -> str:
        return " ".join(
            part
            for part in [
                str(claim.get("claim_text") or claim.get("display_claim_text") or claim.get("canonical_claim_text") or "").strip(),
                str(claim.get("subject") or "").strip(),
                str(claim.get("predicate") or claim.get("predicate_text") or "").strip(),
                str(claim.get("object") or claim.get("object_text") or "").strip(),
            ]
            if part
        )

    @classmethod
    def _feedback_claim_matches(cls, claim: dict[str, Any], claim_text: str) -> bool:
        target = fold_text(claim_text)
        if not target:
            return True
        haystack = fold_text(cls._feedback_claim_text(claim))
        if target in haystack or haystack in target:
            return True
        target_state = cls._feedback_state_object(claim_text)
        claim_object = str(claim.get("object") or claim.get("object_text") or "").strip().lower()
        claim_predicate = fold_text(claim.get("predicate") or claim.get("predicate_text"))
        return bool(target_state and claim_predicate == "active" and claim_object == target_state)

    @staticmethod
    def _feedback_state_object(text: str) -> str | None:
        folded = fold_text(text)
        if re.search(r"\binactive\b|\binaktiv\b|\binaktív\b|\binactivo\b", folded):
            return "false"
        if re.search(r"\bactive\b|\baktiv\b|\baktív\b|\bactivo\b", folded):
            return "true"
        return None

    @classmethod
    def _feedback_new_claim(cls, *, event_id: str, target_entity: str, claim_text: str) -> dict[str, Any]:
        text = str(claim_text or "").strip().rstrip(".")
        folded = fold_text(text)
        source_id = f"feedback-source:{event_id}"
        sentence_id = f"feedback-sentence:{event_id}"
        claim_id = f"feedback-claim:{event_id}"
        state_object = cls._feedback_state_object(text)
        if state_object is not None:
            return {
                "claim_id": claim_id,
                "subject": target_entity,
                "claim_text": text,
                "predicate": "active",
                "predicate_text": "active",
                "object": state_object,
                "object_text": state_object,
                "claim_type": "state",
                "claim_group": "state",
                "status": "active",
                "claim_status": "active",
                "time_mode": "current",
                "time_dominant": "current",
                "time_values": [],
                "sentence_ids": [sentence_id],
                "sentence_text": text + ".",
                "source_ids": [source_id],
                "feedback_weight": 1.0,
                "evidence": {"source_id": source_id, "source_ids": [source_id], "sentence_ids": [sentence_id]},
            }
        rule_match = re.search(r"\b(must|should|required to|kell|kötelező|debe)\b\s+(.+)$", text, flags=re.IGNORECASE)
        if rule_match:
            predicate = rule_match.group(1).strip()
            obj = rule_match.group(2).strip()
            return {
                "claim_id": claim_id,
                "subject": target_entity,
                "claim_text": text,
                "predicate": predicate,
                "predicate_text": predicate,
                "object": obj,
                "object_text": obj,
                "claim_type": "rule_procedure",
                "claim_group": "rule",
                "status": "active",
                "claim_status": "active",
                "time_mode": "timeless",
                "sentence_ids": [sentence_id],
                "sentence_text": text + ".",
                "source_ids": [source_id],
                "feedback_weight": 1.0,
                "evidence": {"source_id": source_id, "source_ids": [source_id], "sentence_ids": [sentence_id]},
            }
        relation_match = re.search(r"\b(uses|use|integrates with|integrates|használ|utiliza|usa)\b\s+(.+)$", text, flags=re.IGNORECASE)
        if relation_match:
            predicate = relation_match.group(1).strip()
            obj = relation_match.group(2).strip()
            return {
                "claim_id": claim_id,
                "subject": target_entity,
                "claim_text": text,
                "predicate": predicate,
                "predicate_text": predicate,
                "object": obj,
                "object_text": obj,
                "claim_group": "relation",
                "status": "active",
                "claim_status": "active",
                "time_mode": "timeless",
                "sentence_ids": [sentence_id],
                "sentence_text": text + ".",
                "source_ids": [source_id],
                "feedback_weight": 1.0,
                "evidence": {"source_id": source_id, "source_ids": [source_id], "sentence_ids": [sentence_id]},
            }
        obj = text
        if cls._feedback_key(target_entity) and folded.startswith(cls._feedback_key(target_entity)):
            obj = text[len(target_entity):].strip()
        return {
            "claim_id": claim_id,
            "subject": target_entity,
            "claim_text": text,
            "predicate": "states",
            "predicate_text": "states",
            "object": obj,
            "object_text": obj,
            "claim_group": "descriptor",
            "status": "active",
            "claim_status": "active",
            "time_mode": "timeless",
            "sentence_ids": [sentence_id],
            "sentence_text": text + ".",
            "source_ids": [source_id],
            "feedback_weight": 1.0,
            "evidence": {"source_id": source_id, "source_ids": [source_id], "sentence_ids": [sentence_id]},
        }

    @staticmethod
    def _weaken_feedback_claim(claim: dict[str, Any]) -> dict[str, Any]:
        updated = dict(claim)
        updated["claim_status"] = "weakened"
        updated["status"] = "weakened"
        updated["feedback_weight"] = max(0.0, float(updated.get("feedback_weight") or 1.0) - 0.5)
        return updated

    @staticmethod
    def _reinforce_feedback_claim(claim: dict[str, Any]) -> dict[str, Any]:
        updated = dict(claim)
        updated["claim_status"] = "active"
        if str(updated.get("status") or "").strip().lower() in {"weakened", "disputed"}:
            updated["status"] = "active"
        updated["feedback_weight"] = min(2.0, float(updated.get("feedback_weight") or 1.0) + 0.25)
        return updated

    def _apply_feedback_to_global_profiles(self, *, corpus_uuid: str, global_profiles: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        events = [event for event in self._feedback_events if event.get("corpus_uuid") == corpus_uuid]
        if not events:
            return global_profiles, []
        profiles = [dict(profile, claims=[dict(claim) for claim in profile.get("claims") or [] if isinstance(claim, dict)]) for profile in global_profiles]
        applied_events: list[dict[str, Any]] = []
        for event in events:
            target_key = self._feedback_key(event.get("target_entity"))
            if not target_key:
                continue
            for profile in profiles:
                profile_key = self._feedback_key(profile.get("canonical_key") or profile.get("entity_name"))
                if profile_key != target_key:
                    continue
                affected: list[str] = []
                claims = []
                for claim in profile.get("claims") or []:
                    claim_id = str(claim.get("claim_id") or "").strip()
                    if self._feedback_claim_matches(claim, str(event.get("claim_text") or "")):
                        affected.append(claim_id)
                        if event.get("feedback_type") in {"incorrect", "replace"}:
                            claim = self._weaken_feedback_claim(claim)
                        elif event.get("feedback_type") == "correct":
                            claim = self._reinforce_feedback_claim(claim)
                    claims.append(claim)
                new_claim_ids: list[str] = []
                if event.get("feedback_type") == "replace" and event.get("optional_new_claim"):
                    new_claim = self._feedback_new_claim(
                        event_id=str(event.get("feedback_event_id")),
                        target_entity=str(event.get("target_entity") or profile.get("entity_name") or ""),
                        claim_text=str(event.get("optional_new_claim") or ""),
                    )
                    claims.append(new_claim)
                    new_claim_ids.append(str(new_claim.get("claim_id") or ""))
                profile["claims"] = claims
                applied = {**event, "affected_claim_ids": affected, "new_claim_ids": new_claim_ids}
                applied_events.append(applied)
        return profiles, applied_events

    def apply_knowledge_feedback(
        self,
        *,
        tenant: str,
        corpus_uuid: str,
        target_entity: str,
        claim_text: str,
        feedback_type: str,
        optional_new_claim: str | None = None,
        user_input: str | None = None,
        user_id: int | None = None,
    ) -> dict[str, Any]:
        normalized_type = str(feedback_type or "").strip().lower()
        if normalized_type not in {"correct", "incorrect", "replace"}:
            raise ValueError("feedback_type must be one of: correct, incorrect, replace")
        if normalized_type == "replace" and not str(optional_new_claim or "").strip():
            raise ValueError("optional_new_claim is required for replace feedback")
        event = {
            "feedback_event_id": str(uuid_lib.uuid4()),
            "tenant": tenant,
            "corpus_uuid": corpus_uuid,
            "target_entity": str(target_entity or "").strip(),
            "claim_text": str(claim_text or "").strip(),
            "feedback_type": normalized_type,
            "optional_new_claim": str(optional_new_claim or "").strip() or None,
            "user_input": user_input or str(optional_new_claim or claim_text or "").strip(),
            "user_id": user_id,
            "created_at": _utcnow().isoformat(),
            "affected_claim_ids": [],
            "new_claim_ids": [],
        }
        self._feedback_events.append(event)
        global_profiles = self._load_existing_global_profiles(corpus_uuid=corpus_uuid, exclude_interpretation_run_id=None)
        _, applied_events = self._apply_feedback_to_global_profiles(corpus_uuid=corpus_uuid, global_profiles=global_profiles)
        applied = next((item for item in reversed(applied_events) if item.get("feedback_event_id") == event["feedback_event_id"]), event)
        self._log_step("knowledge.feedback.apply", status="ok", tenant=tenant, corpus_uuid=corpus_uuid, feedback_type=normalized_type)
        return {"feedback_event": applied}

    @staticmethod
    def _claim_source_ids_for_withdrawal(claim: dict[str, Any]) -> list[str]:
        evidence = claim.get("evidence") if isinstance(claim.get("evidence"), dict) else {}
        ids: list[str] = []
        for value in [
            claim.get("source_id"),
            evidence.get("source_id"),
            *(claim.get("source_ids") or []),
            *(evidence.get("source_ids") or []),
        ]:
            text = str(value or "").strip()
            if text and text not in ids:
                ids.append(text)
        return ids

    @staticmethod
    def _withdraw_claim(claim: dict[str, Any]) -> dict[str, Any]:
        updated = dict(claim)
        updated["claim_status"] = "withdrawn"
        updated["status"] = "withdrawn"
        updated["feedback_weight"] = 0.0
        return updated

    def _apply_source_withdrawals_to_global_profiles(
        self,
        *,
        corpus_uuid: str,
        global_profiles: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        events = [event for event in self._source_withdrawal_events if event.get("corpus_uuid") == corpus_uuid]
        if not events:
            return global_profiles, []
        profiles = [dict(profile, claims=[dict(claim) for claim in profile.get("claims") or [] if isinstance(claim, dict)]) for profile in global_profiles]
        applied_events: list[dict[str, Any]] = []
        for event in events:
            source_id = str(event.get("source_id") or "").strip()
            if not source_id:
                continue
            affected_claim_ids: list[str] = []
            affected_profile_ids: list[str] = []
            for profile in profiles:
                claims: list[dict[str, Any]] = []
                profile_touched = False
                for claim in profile.get("claims") or []:
                    if source_id in self._claim_source_ids_for_withdrawal(claim):
                        claim = self._withdraw_claim(claim)
                        claim_id = str(claim.get("claim_id") or "").strip()
                        if claim_id and claim_id not in affected_claim_ids:
                            affected_claim_ids.append(claim_id)
                        profile_touched = True
                    claims.append(claim)
                if profile_touched:
                    profile_id = str(profile.get("profile_id") or "").strip()
                    if profile_id and profile_id not in affected_profile_ids:
                        affected_profile_ids.append(profile_id)
                profile["claims"] = claims
            applied_events.append(
                {
                    **event,
                    "affected_claim_ids": affected_claim_ids,
                    "affected_profile_ids": affected_profile_ids,
                }
            )
        return profiles, applied_events

    def withdraw_source(
        self,
        *,
        tenant: str,
        corpus_uuid: str,
        source_id: str,
        user_input: str | None = None,
        user_id: int | None = None,
    ) -> dict[str, Any]:
        normalized_source_id = str(source_id or "").strip()
        if not normalized_source_id:
            raise ValueError("source_id is required")
        event = {
            "source_withdrawal_event_id": str(uuid_lib.uuid4()),
            "tenant": tenant,
            "corpus_uuid": corpus_uuid,
            "source_id": normalized_source_id,
            "user_input": user_input or f"withdraw_source({normalized_source_id})",
            "user_id": user_id,
            "created_at": _utcnow().isoformat(),
            "affected_claim_ids": [],
            "affected_profile_ids": [],
        }
        self._source_withdrawal_events.append(event)
        source = self._source_store.get(normalized_source_id)
        if source is not None:
            metadata = dict(source.metadata or {})
            metadata.update(
                {
                    "withdrawn": True,
                    "withdrawn_at": event["created_at"],
                    "withdrawn_by": user_id,
                }
            )
            self._source_store.update(replace(source, metadata=metadata))
        global_profiles = self._load_existing_global_profiles(corpus_uuid=corpus_uuid, exclude_interpretation_run_id=None)
        _, applied_events = self._apply_source_withdrawals_to_global_profiles(corpus_uuid=corpus_uuid, global_profiles=global_profiles)
        applied = next((item for item in reversed(applied_events) if item.get("source_withdrawal_event_id") == event["source_withdrawal_event_id"]), event)
        self._log_step("knowledge.source.withdraw", status="ok", tenant=tenant, corpus_uuid=corpus_uuid, source_id=normalized_source_id)
        return {"source_withdrawal_event": applied}

    def _enrich_matched_claims_for_explanation(self, matched_claims: list[dict[str, Any]]) -> list[dict[str, Any]]:
        enriched: list[dict[str, Any]] = []
        sentence_cache: dict[str, Any] = {}
        for claim in matched_claims:
            row = dict(claim)
            sentence_ids = [str(item).strip() for item in row.get("sentence_ids") or [] if str(item or "").strip()]
            sentence_texts: list[str] = []
            source_ids = [str(item).strip() for item in row.get("source_ids") or [] if str(item or "").strip()]
            for sentence_id in sentence_ids:
                if sentence_id not in sentence_cache:
                    sentence_cache[sentence_id] = self._sentence_store.get(sentence_id)
                sentence = sentence_cache.get(sentence_id)
                sentence_text = str(getattr(sentence, "text_content", "") or "").strip()
                if sentence_text:
                    sentence_texts.append(sentence_text)
                source_id = str(getattr(sentence, "source_id", "") or "").strip()
                if source_id and source_id not in source_ids:
                    source_ids.append(source_id)
            if sentence_texts:
                row["sentence_text"] = sentence_texts[0]
                row["sentence_texts"] = sentence_texts
            if source_ids:
                row["source_ids"] = source_ids
            enriched.append(row)
        return enriched

    def _build_lineage_graph(self, *, corpus_uuid: str) -> dict[str, Any]:
        global_profiles = self._load_existing_global_profiles(
            corpus_uuid=corpus_uuid,
            exclude_interpretation_run_id=None,
        )
        global_profiles, feedback_events = self._apply_feedback_to_global_profiles(
            corpus_uuid=corpus_uuid,
            global_profiles=global_profiles,
        )
        global_profiles, source_withdrawal_events = self._apply_source_withdrawals_to_global_profiles(
            corpus_uuid=corpus_uuid,
            global_profiles=global_profiles,
        )
        retrieval_chunks = (
            RetrievalChunkBuilderV0().build_many(global_profiles, [])
            if feedback_events or source_withdrawal_events
            else self._load_existing_retrieval_chunks(
                corpus_uuid=corpus_uuid,
                exclude_interpretation_run_id=None,
            )
        )
        graph = LineageBuilderV0().build(global_profiles=global_profiles, retrieval_chunks=retrieval_chunks)
        graph["feedback_events"] = feedback_events
        graph["source_withdrawal_events"] = source_withdrawal_events
        return graph

    def get_lineage(
        self,
        *,
        corpus_uuid: str,
        claim_id: str | None = None,
        profile_id: str | None = None,
    ) -> dict[str, Any]:
        target_type = "claim" if claim_id else "global_profile"
        target_id = str(claim_id or profile_id or "").strip()
        if not target_id:
            raise ValueError("claim_id or profile_id is required")
        graph = self._build_lineage_graph(corpus_uuid=corpus_uuid)
        focused = LineageBuilderV0().focus(graph, target_type=target_type, target_id=target_id)
        focused["corpus_uuid"] = corpus_uuid
        return focused

    def get_quality_report(self, *, corpus_uuid: str) -> dict[str, Any]:
        global_profiles = self._load_existing_global_profiles(
            corpus_uuid=corpus_uuid,
            exclude_interpretation_run_id=None,
        )
        global_profiles, feedback_events = self._apply_feedback_to_global_profiles(
            corpus_uuid=corpus_uuid,
            global_profiles=global_profiles,
        )
        global_profiles, source_withdrawal_events = self._apply_source_withdrawals_to_global_profiles(
            corpus_uuid=corpus_uuid,
            global_profiles=global_profiles,
        )
        report = KnowledgeQualityReportV0().build(corpus_uuid=corpus_uuid, global_profiles=global_profiles)
        report["feedback_events"] = feedback_events
        report["source_withdrawal_events"] = source_withdrawal_events
        return report

    async def retrieve(
        self,
        *,
        tenant: str,
        corpus_uuid: str,
        query: str,
        build_ids: list[str] | None = None,
        retrieval_profile: RetrievalProfile | None = None,
        context_profile: ContextProfile | None = None,
        compare_mode: bool = False,
    ) -> QueryRun:
        started = time.perf_counter()
        retrieval = retrieval_profile or DEFAULT_RETRIEVAL_PROFILE
        context = context_profile or DEFAULT_CONTEXT_PROFILE
        query_profile = query_profile_to_json_dict(QueryResolverV0().resolve(query))
        builds = self._resolve_builds(corpus_uuid=corpus_uuid, build_ids=build_ids)
        no_ready_index_build = not builds
        hits = []
        if builds:
            hits = await self._retrieve_hits_with_resilience(
                tenant=tenant,
                corpus_uuid=corpus_uuid,
                query=query,
                builds=builds,
                retrieval_profile=retrieval,
                query_profile=query_profile,
            )
            if retrieval.score_threshold is not None:
                hits = [
                    item for item in hits if float(item.get("fusion_score") or item.get("score") or 0.0) >= retrieval.score_threshold
                ]
        query_global_profiles = self._load_existing_global_profiles(
            corpus_uuid=corpus_uuid,
            exclude_interpretation_run_id=None,
        )
        query_global_profiles, feedback_events = self._apply_feedback_to_global_profiles(
            corpus_uuid=corpus_uuid,
            global_profiles=query_global_profiles,
        )
        query_global_profiles, source_withdrawal_events = self._apply_source_withdrawals_to_global_profiles(
            corpus_uuid=corpus_uuid,
            global_profiles=query_global_profiles,
        )
        query_retrieval_chunks = (
            RetrievalChunkBuilderV0().build_many(query_global_profiles, [])
            if feedback_events or source_withdrawal_events
            else self._load_existing_retrieval_chunks(
                corpus_uuid=corpus_uuid,
                exclude_interpretation_run_id=None,
            )
        )
        query_retrieval_chunks = self._order_chunks_by_vector_hits(query_retrieval_chunks, hits)
        query_aware_result = QueryAwareRetrievalV0().match(
            query_profile=query_profile,
            retrieval_chunks=query_retrieval_chunks,
            global_profiles=query_global_profiles,
        )
        matched_chunks = list(query_aware_result.get("matched_chunks") or [])
        matched_claims = self._enrich_matched_claims_for_explanation(list(query_aware_result.get("matched_claims") or []))
        query_aware_result["matched_claims"] = matched_claims
        semantic_blocks = self._load_existing_semantic_blocks(
            corpus_uuid=corpus_uuid,
            exclude_interpretation_run_id=None,
        )
        vector_matched_semantic_blocks = self._semantic_blocks_from_vector_hits(hits)
        lexical_matched_semantic_blocks = self._select_semantic_blocks_for_query(
            semantic_blocks=semantic_blocks,
            matched_claims=matched_claims,
            matched_chunks=matched_chunks,
            query_profile=query_profile,
            query=query,
        )
        matched_semantic_blocks: list[dict[str, Any]] = []
        seen_block_ids: set[str] = set()
        for block in [*vector_matched_semantic_blocks, *lexical_matched_semantic_blocks]:
            block_id = str(block.get("id") or "").strip()
            if not block_id or block_id in seen_block_ids:
                continue
            seen_block_ids.add(block_id)
            matched_semantic_blocks.append(block)
            if len(matched_semantic_blocks) >= 4:
                break
        synthesis_result = SynthesisEngineV0().synthesize(
            query_profile=query_profile,
            matched_chunks=matched_chunks,
            matched_claims=matched_claims,
        )
        answer_mode = str(synthesis_result.get("answer_mode") or "no_answer")
        conflict_marker_included = (
            bool(query_aware_result.get("conflict_marker_included"))
            or answer_mode == "conflict"
            or any(bool(item.get("conflict_marker")) for item in matched_claims)
        )
        evidence_summary = synthesis_result.get("evidence_summary") or (synthesis_result.get("synthesis_debug") or {}).get("evidence") or []
        block_evidence_summary = [
            {
                "block_id": str(block.get("id") or ""),
                "source_id": str(block.get("source_id") or ""),
                "document_id": str(block.get("document_id") or ""),
                "subject": str(block.get("primary_subject") or ""),
                "space": str(block.get("primary_space") or ", ".join(block.get("space_values") or []) or ""),
                "time": str(block.get("primary_time") or ", ".join(block.get("time_values") or []) or ""),
                "sentence_ids": list(block.get("sentence_ids") or []),
                "claim_ids": list(block.get("claim_ids") or []),
                "summary": str(block.get("summary") or ""),
                "snippet": str(block.get("text") or "")[:500],
                "match_score": block.get("match_score") or 0.0,
                "match_reason": block.get("match_reason") or {},
                "block_status": block.get("block_status") or (block.get("metadata") or {}).get("block_status") or "draft",
                "source_reliability": block.get("source_reliability") or (block.get("metadata") or {}).get("source_reliability") or 0.0,
                "retrieval_weight": block.get("retrieval_weight") or (block.get("metadata") or {}).get("retrieval_weight") or 1.0,
                "conflict_count": block.get("conflict_count") or (block.get("metadata") or {}).get("conflict_count") or 0,
                "conflicts": list(block.get("conflicts") or (block.get("metadata") or {}).get("conflicts") or []),
            }
            for block in matched_semantic_blocks
        ]
        explanation_payload = ExplanationBuilderV0().build(
            answer_text=str(synthesis_result.get("answer_text") or ""),
            matched_claims=matched_claims,
            cited_claim_ids=list(synthesis_result.get("cited_claim_ids") or []),
            cited_sentence_ids=list(synthesis_result.get("cited_sentence_ids") or []),
            cited_source_ids=list(synthesis_result.get("cited_source_ids") or synthesis_result.get("source_ids") or []),
        )
        explanation = explanation_payload.get("explanation") or {}
        verification = verify_answer(str(synthesis_result.get("answer_text") or ""), block_evidence_summary)
        answer_verification = {
            "is_grounded": verification.is_grounded,
            "has_evidence": verification.has_evidence,
            "mentions_conflict": verification.mentions_conflict,
            "invented_terms": list(verification.invented_terms),
            "context_block_count": len(matched_semantic_blocks),
            "warning": None
            if verification.is_grounded or matched_semantic_blocks
            else "A válaszhoz nincs elég erős, visszakövethető bizonyíték.",
        }
        lineage_builder = LineageBuilderV0()
        lineage_graph = lineage_builder.build(global_profiles=query_global_profiles, retrieval_chunks=query_retrieval_chunks)
        lineage_debug = {
            "cited_claims": [
                lineage_builder.focus(lineage_graph, target_type="claim", target_id=str(claim_id))
                for claim_id in synthesis_result.get("cited_claim_ids") or []
            ],
            "matched_profiles": [
                lineage_builder.focus(lineage_graph, target_type="global_profile", target_id=str(chunk.get("profile_id") or ""))
                for chunk in matched_chunks
                if str(chunk.get("profile_id") or "").strip()
            ],
        }
        query_debug = {
            "endpoint_called": "facade.retrieve",
            "query_text": query,
            "query_profile": query_profile,
            "matched_chunks_count": len(matched_chunks),
            "matched_claims_count": len(matched_claims),
            "matched_semantic_blocks_count": len(matched_semantic_blocks),
            "vector_matched_semantic_blocks_count": len(vector_matched_semantic_blocks),
            "conflict_marker_included": conflict_marker_included,
            "temporal_context_used": bool(query_aware_result.get("temporal_context_used")),
            "synthesis_called": True,
            "answer_text": synthesis_result.get("answer_text") or "",
            "answer_mode": answer_mode,
            "cited_claim_ids": synthesis_result.get("cited_claim_ids") or [],
            "cited_sentence_ids": synthesis_result.get("cited_sentence_ids") or [],
            "cited_source_ids": synthesis_result.get("cited_source_ids") or synthesis_result.get("source_ids") or [],
            "evidence": evidence_summary,
            "context_blocks": block_evidence_summary,
            "explanation": explanation,
            "answer_verification": answer_verification,
            "matched_semantic_blocks": matched_semantic_blocks,
            "lineage": lineage_debug,
            "no_ready_index_build": no_ready_index_build,
            "feedback_events": feedback_events,
            "source_withdrawal_events": source_withdrawal_events,
            "response_contains_answer_text": bool(synthesis_result.get("answer_text")),
        }

        context_text, selected = self._context_builder.build_context(
            query=query,
            hits=hits,
            context_profile=context,
            query_run_id="pending",
        )
        semantic_context_text = self._semantic_blocks_context(matched_semantic_blocks)
        if semantic_context_text:
            context_text = f"{semantic_context_text}\n\n[Vectoros találatok]\n{context_text}" if context_text else semantic_context_text
        citations = [
            Citation(
                source_id=str((item.get("payload") or {}).get("source_id") or ""),
                build_id=str(item.get("build_id") or ""),
                snippet=str((item.get("payload") or {}).get("text") or "")[:400],
                score=float(item.get("fusion_score") or item.get("score") or 0.0),
                title=(item.get("payload") or {}).get("source_title"),
                chunk_id=str((item.get("payload") or {}).get("block_id") or item.get("id") or ""),
                metadata={
                    "profile": item.get("build_key"),
                    "point_type": (item.get("payload") or {}).get("point_type"),
                },
            )
            for item in selected
        ]
        latency_ms = (time.perf_counter() - started) * 1000.0
        query_run = QueryRun(
            tenant=tenant,
            query=query,
            corpus_uuid=corpus_uuid,
            build_ids=[item.id for item in builds],
            retrieval_profile_key=retrieval.key,
            context_profile_key=context.key,
            latency_ms=round(latency_ms, 2),
            result_count=len(hits),
            citations=citations,
            context_text=context_text,
            compare_mode=compare_mode,
            metadata=_json_safe({
                "selected_citation_count": len(citations),
                "query_profile": query_profile,
                "query_detected_entities": query_profile.get("detected_entities") or [],
                "query_intent": query_profile.get("intent") or "unknown",
                "query_filters": {
                    "entity_type": query_profile.get("entity_type"),
                    "entity": query_profile.get("entity"),
                    "state": query_profile.get("state"),
                    "time_filter": query_profile.get("time_filter"),
                    "space_filter": query_profile.get("space_filter"),
                    "keywords": query_profile.get("keywords") or [],
                },
                "query_resolution_confidence": query_profile.get("confidence") or 0.0,
                "no_ready_index_build": no_ready_index_build,
                "query_aware_retrieval": query_aware_result,
                "feedback_events": feedback_events,
                "source_withdrawal_events": source_withdrawal_events,
                "matched_chunks": matched_chunks,
                "matched_claims": matched_claims,
                "matched_semantic_blocks": matched_semantic_blocks,
                "vector_matched_semantic_blocks": vector_matched_semantic_blocks,
                "filtered_out_reason": query_aware_result.get("filtered_out_reason") or [],
                "retrieval_confidence": query_aware_result.get("retrieval_confidence") or 0.0,
                "query_retrieval_match_count": query_aware_result.get("query_retrieval_match_count") or 0,
                "query_retrieval_filtered_count": query_aware_result.get("query_retrieval_filtered_count") or 0,
                "conflict_marker_included": conflict_marker_included,
                "temporal_context_used": bool(query_aware_result.get("temporal_context_used")),
                "synthesis": synthesis_result,
                "synthesis_called": True,
                "answer_text": synthesis_result.get("answer_text") or "",
                "answer_mode": answer_mode,
                "cited_claim_ids": synthesis_result.get("cited_claim_ids") or [],
                "cited_evidence_ids": synthesis_result.get("cited_evidence_ids") or [],
                "cited_sentence_ids": synthesis_result.get("cited_sentence_ids") or [],
                "cited_source_ids": synthesis_result.get("cited_source_ids") or synthesis_result.get("source_ids") or [],
                "source_ids": synthesis_result.get("source_ids") or [],
                "evidence_summary": evidence_summary,
                "context_blocks": block_evidence_summary,
                "explanation": explanation,
                "answer_verification": answer_verification,
                "explanation_payload": explanation_payload,
                "lineage": lineage_debug,
                "synthesis_confidence": synthesis_result.get("synthesis_confidence") or 0.0,
                "query_debug": query_debug,
            }),
        )
        saved = self._query_run_store.save(query_run)
        self._metrics_store.increment("query_count", 1)
        self._metrics_store.record_timing("query_latency_ms", latency_ms)
        self._metrics_store.increment("query_result_count_total", len(hits))
        self._metrics_store.increment("context_char_total", len(context_text))
        self._log_step(
            "query.run.save",
            status="ok",
            tenant=tenant,
            query_run_id=saved.id,
            duration_ms=latency_ms,
            result_count=len(hits),
            build_count=len(builds),
        )
        return saved

    async def build_chat_context(
        self,
        *,
        tenant: str | None = None,
        corpus_uuid: str | None = None,
        query: str | None = None,
        build_ids: list[str] | None = None,
        retrieval_profile: RetrievalProfile | None = None,
        context_profile: ContextProfile | None = None,
        question: str | None = None,
        kb_uuid: str | None = None,
        current_user_id: int | None = None,
        current_user_role: str | None = None,
        parsed_query: dict[str, Any] | None = None,
        debug: bool = False,
    ) -> dict[str, Any]:
        effective_query = str(query or question or "").strip()
        effective_corpus_uuid = str(corpus_uuid or kb_uuid or "").strip()
        if not effective_query:
            raise ValueError("Query is required for chat context build")
        if not effective_corpus_uuid:
            raise ValueError("Corpus UUID is required for chat context build")
        run = await self.retrieve(
            tenant=tenant or "",
            corpus_uuid=effective_corpus_uuid,
            query=effective_query,
            build_ids=build_ids,
            retrieval_profile=retrieval_profile,
            context_profile=context_profile,
            compare_mode=len(build_ids or []) > 1,
        )
        source_metadata_by_id: dict[str, Source] = {}
        for source_id in run.metadata.get("cited_source_ids") or run.metadata.get("source_ids") or []:
            source = self._source_store.get(str(source_id))
            if source is not None:
                source_metadata_by_id[source.id] = source
        for block in run.metadata.get("context_blocks") or run.metadata.get("matched_semantic_blocks") or []:
            if not isinstance(block, dict):
                continue
            source_id = str(block.get("source_id") or "").strip()
            if not source_id or source_id in source_metadata_by_id:
                continue
            source = self._source_store.get(source_id)
            if source is not None:
                source_metadata_by_id[source.id] = source
        for citation in run.citations:
            if citation.source_id and citation.source_id not in source_metadata_by_id:
                source = self._source_store.get(citation.source_id)
                if source is not None:
                    source_metadata_by_id[source.id] = source
        source_chunks = [
            {
                "id": citation.chunk_id or f"source-{index}",
                "kb_uuid": effective_corpus_uuid,
                "source_point_id": citation.source_id or citation.chunk_id or f"source-{index}",
                "source_id": citation.source_id or "",
                "source_document_title": citation.title or "",
                "text": citation.snippet,
                "score": citation.score,
                "build_id": citation.build_id,
                "source_type": getattr(source_metadata_by_id.get(citation.source_id), "source_type", ""),
                "file_ref": getattr(source_metadata_by_id.get(citation.source_id), "file_ref", None),
                "display_type": (
                    self._source_display_type(source_metadata_by_id[citation.source_id])
                    if citation.source_id in source_metadata_by_id
                    else ""
                ),
                "created_by": getattr(source_metadata_by_id.get(citation.source_id), "created_by", None),
                "created_by_label": (
                    self._source_created_by_label(source_metadata_by_id[citation.source_id])
                    if citation.source_id in source_metadata_by_id
                    else ""
                ),
            }
            for index, citation in enumerate(run.citations, start=1)
        ]
        existing_source_chunk_ids = {
            str(item.get("source_id") or item.get("source_point_id") or "").strip()
            for item in source_chunks
        }
        for source_id, source in source_metadata_by_id.items():
            if source_id in existing_source_chunk_ids:
                continue
            document = self._document_store.get_for_source(source_id)
            source_chunks.append(
                {
                    "id": f"source-{source_id}",
                    "kb_uuid": effective_corpus_uuid,
                    "source_point_id": source_id,
                    "source_id": source_id,
                    "source_document_title": source.title,
                    "text": (document.text_content if document is not None else str(source.raw_content or ""))[:400],
                    "score": 0.0,
                    "build_id": "",
                    "source_type": source.source_type,
                    "file_ref": source.file_ref,
                    "display_type": self._source_display_type(source),
                    "created_by": source.created_by,
                    "created_by_label": self._source_created_by_label(source),
                }
            )
        return {
            "query_run_id": run.id,
            "kb_uuid": effective_corpus_uuid,
            "corpus_uuid": effective_corpus_uuid,
            "context_text": run.context_text,
            "citations": [
                {
                    "source_id": item.source_id,
                    "build_id": item.build_id,
                    "snippet": item.snippet,
                    "title": item.title,
                    "score": item.score,
                    "chunk_id": item.chunk_id,
                }
                for item in run.citations
            ],
            "build_ids": run.build_ids,
            "retrieval_profile_key": run.retrieval_profile_key,
            "context_profile_key": run.context_profile_key,
            "query_profile": run.metadata.get("query_profile"),
            "query_detected_entities": run.metadata.get("query_detected_entities") or [],
            "query_intent": run.metadata.get("query_intent"),
            "query_filters": run.metadata.get("query_filters") or {},
            "query_resolution_confidence": run.metadata.get("query_resolution_confidence") or 0.0,
            "query_aware_retrieval": run.metadata.get("query_aware_retrieval") or {},
            "matched_chunks": run.metadata.get("matched_chunks") or [],
            "matched_claims": run.metadata.get("matched_claims") or [],
            "matched_semantic_blocks": run.metadata.get("matched_semantic_blocks") or [],
            "filtered_out_reason": run.metadata.get("filtered_out_reason") or [],
            "retrieval_confidence": run.metadata.get("retrieval_confidence") or 0.0,
            "query_retrieval_match_count": run.metadata.get("query_retrieval_match_count") or 0,
            "query_retrieval_filtered_count": run.metadata.get("query_retrieval_filtered_count") or 0,
            "conflict_marker_included": bool(run.metadata.get("conflict_marker_included")),
            "temporal_context_used": bool(run.metadata.get("temporal_context_used")),
            "answer_text": run.metadata.get("answer_text") or "",
            "answer_mode": run.metadata.get("answer_mode") or "no_answer",
            "cited_claim_ids": run.metadata.get("cited_claim_ids") or [],
            "cited_evidence_ids": run.metadata.get("cited_evidence_ids") or [],
            "cited_sentence_ids": run.metadata.get("cited_sentence_ids") or [],
            "cited_source_ids": run.metadata.get("cited_source_ids") or run.metadata.get("source_ids") or [],
            "source_ids": run.metadata.get("source_ids") or [],
            "evidence_summary": run.metadata.get("evidence_summary") or [],
            "explanation": run.metadata.get("explanation") or {},
            "lineage": run.metadata.get("lineage") or {},
            "synthesis_confidence": run.metadata.get("synthesis_confidence") or 0.0,
            "query_debug": run.metadata.get("query_debug") or {},
            "no_ready_index_build": bool(run.metadata.get("no_ready_index_build")),
            "top_assertions": [],
            "evidence_sentences": [],
            "source_chunks": source_chunks,
            "related_entities": [],
            "scoring_summary": {
                "latency_ms": {"retrieve": run.latency_ms},
                "result_count": run.result_count,
            },
            "query_focus": parsed_query or {},
            "debug_enabled": debug,
            "current_user_id": current_user_id,
            "current_user_role": current_user_role,
        }

    async def answer_support(
        self,
        *,
        tenant: str,
        corpus_uuid: str,
        query: str,
        build_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        packet = await self.build_chat_context(
            tenant=tenant,
            corpus_uuid=corpus_uuid,
            query=query,
            build_ids=build_ids,
        )
        return {
            "question": query,
            "context_text": packet["context_text"],
            "citations": packet["citations"],
        }

    def get_metrics(self) -> dict[str, object]:
        return self._metrics_store.snapshot()


__all__ = ["KnowledgeFacade"]
