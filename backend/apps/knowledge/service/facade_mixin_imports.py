from __future__ import annotations

from collections.abc import Callable
import logging
import re
import time
import threading
import uuid as uuid_lib
from dataclasses import replace
from datetime import datetime
from typing import Any

from apps.knowledge.domain.context_profile import ContextProfile
from apps.knowledge.domain.claim import Claim
from apps.knowledge.domain.corpus import Corpus
from apps.knowledge.domain.document import Document
from apps.knowledge.domain.ingest_event import IngestEvent
from apps.knowledge.domain.ingest_input import IngestInput
from apps.knowledge.domain.ingest_item import IngestItem
from apps.knowledge.domain.ingest_run import IngestRun
from apps.knowledge.domain.local_entity_cluster import LocalEntityCluster
from apps.knowledge.domain.index_build import IndexBuild
from apps.knowledge.domain.index_profile import IndexProfile
from apps.knowledge.domain.interpretation_run import InterpretationRun
from apps.knowledge.domain.mention import Mention
from apps.knowledge.domain.paragraph import Paragraph
from apps.knowledge.domain.parser_run import ParserRun
from apps.knowledge.domain.query_run import QueryRun
from apps.knowledge.domain.retrieval_profile import RetrievalProfile
from apps.knowledge.domain.sentence import Sentence
from apps.knowledge.domain.sentence_interpretation import SentenceInterpretation
from apps.knowledge.domain.source import Source
from apps.knowledge.domain.space_time_frame import SpaceTimeFrame
from apps.knowledge.errors import IngestRunNotFound, KnowledgeSourceNotFound, KnowledgeValidationError
from apps.knowledge.service.facade_helpers import (
    SentenceCandidate,
    aggregate_ingest_item_quality as _aggregate_ingest_item_quality,
    is_uuid_string as _is_uuid_string,
    truncate_diagnostic_text as _truncate_diagnostic_text,
    utcnow as _utcnow,
)
from apps.knowledge.service.claim_split import ClaimFineSplitter
from apps.knowledge.service.claim_extractor_v1 import ClaimExtractorV1
from apps.knowledge.service.claim_payload_builder import ClaimPayloadBuilder
from apps.knowledge.service.claim_quality_gate import ClaimQualityGate
from apps.knowledge.service.chunking_service import ChunkingService
from apps.knowledge.service.corpus_management_service import CorpusManagementService
from apps.knowledge.service.knowledge_audit_service import KnowledgeAuditService
from apps.knowledge.service.knowledge_permission_service import KnowledgePermissionService
from apps.knowledge.service.knowledge_trace_service import KnowledgeTraceService
from apps.knowledge.service.language_rules import detect_language, resolve_language
from apps.knowledge.service.mention_extractor import MentionExtractor, debug_print as debug_print_mentions
from apps.knowledge.service.local_resolver_v1 import LocalResolverV1
from apps.knowledge.service.semantic_block_selection import (
    filter_relevant_semantic_blocks,
    is_broad_function_query,
    order_chunks_by_vector_hits,
    query_phrase_for_blocks,
    query_terms_for_blocks,
    retrieval_chunks_from_vector_hits,
    select_semantic_blocks_for_query,
    semantic_block_search_text,
    semantic_blocks_context,
    semantic_blocks_from_vector_hits,
)
from apps.knowledge.service.space_time_extractor_v1 import SpaceTimeExtractorV1
from apps.knowledge.service.url_fetch_service import UrlFetchService
from apps.knowledge.domain.search_profile import SearchProfile
from apps.knowledge.service.document_interpretation_service import DocumentInterpretationService
from apps.knowledge.service.semantic_block_quality_v0 import enrich_semantic_blocks_with_quality
from apps.knowledge.service.knowledge_feedback_service import KnowledgeFeedbackService
from apps.knowledge.service.knowledge_lineage_service import KnowledgeLineageDependencies, KnowledgeLineageService
from apps.knowledge.service.knowledge_report_service import KnowledgeReportDependencies, KnowledgeReportService
from apps.knowledge.service.knowledge_cleanup_service import KnowledgeCleanupDependencies, KnowledgeCleanupService
from apps.knowledge.service.knowledge_pii_service import KnowledgePiiService
from apps.knowledge.service.ingest_progress_service import IngestProgressService
from apps.knowledge.service.ingest_run_creation_service import IngestRunCreationDependencies, IngestRunCreationService
from apps.knowledge.service.ingest_run_service import IngestRunService
from apps.knowledge.service.index_profile_support import IndexProfileSupport
from apps.knowledge.service.index_build_service import IndexBuildService
from apps.knowledge.service.ingest_item_processor import IngestItemProcessor, IngestItemProcessorDependencies
from apps.knowledge.service.ingest_listing_service import IngestListingService
from apps.knowledge.service.ingest_run_processor import IngestRunProcessor, IngestRunProcessorDependencies
from apps.knowledge.service.information_value_scorer import InformationValueScorer
from apps.knowledge.service.mention_resolution_service import MentionResolutionService
from apps.knowledge.service.parser_orchestrator import ParserOrchestrator
from apps.knowledge.service.profile_history_service import ProfileHistoryService
from apps.knowledge.service.source_storage_service import SourceStorageService
from apps.knowledge.service.source_access_service import SourceAccessService
from apps.knowledge.service.retrieval_service import RetrievalService, RetrievalServiceDependencies
from apps.knowledge.service.sentence_unit_builder import SentenceUnitBuilder
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
from core.modules.users.domain.dto import User
from core.kernel.interface.observability import (
    increment_metric as increment_platform_metric,
    observability_scope,
)
from core.kernel.config.config_loader import settings
from shared.documents import ExtractedDocument, ExtractedParagraph, extract_document_from_upload, extract_text_from_upload
from shared.object_storage.contracts import ObjectStoragePort
from sqlalchemy.exc import ProgrammingError


logger = logging.getLogger(__name__)

__all__ = [name for name in globals() if not name.startswith("__")]
