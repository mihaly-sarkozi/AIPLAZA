from __future__ import annotations

from types import SimpleNamespace

import pytest

from apps.knowledge.errors import (
    IngestRunNotFound,
    KnowledgeSourceNotFound,
    KnowledgeSourceUnavailable,
    KnowledgeValidationError,
)
from apps.knowledge.service.ingest_run_processor import IngestRunProcessor
from apps.knowledge.service.knowledge_feedback_service import KnowledgeFeedbackService
from apps.knowledge.service.knowledge_lineage_service import KnowledgeLineageService
from apps.knowledge.service.parser_orchestrator import ParserOrchestrator

pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


def test_ingest_run_processor_raises_module_not_found_error() -> None:
    facade = SimpleNamespace(_ingest_run_store=SimpleNamespace(get=lambda _run_id: None))
    processor = IngestRunProcessor(facade, item_processor=object())

    with pytest.raises(IngestRunNotFound):
        processor.process_run("missing")


def test_parser_orchestrator_raises_module_source_not_found_error() -> None:
    parser = ParserOrchestrator(
        source_store=SimpleNamespace(get=lambda _source_id: None),
        parser_run_store=None,
        document_store=None,
        paragraph_store=None,
        sentence_store=None,
        extract_parser_document_from_source=lambda *_args, **_kwargs: None,
        delete_source_parse_outputs=lambda _source_id: None,
        normalize_parser_text=lambda value: str(value or ""),
        describe_empty_extraction=lambda _metadata: "empty",
        split_paragraphs=lambda _text: [],
        build_claim_refinement_budget=lambda _count: 0,
        build_sentence_units_for_paragraph_with_diagnostics=lambda *_args, **_kwargs: ([], {}),
        interpret_document=lambda *_args, **_kwargs: None,
        truncate_error_message=lambda value, **_kwargs: str(value),
        log_step=lambda *_args, **_kwargs: None,
        parser_error_message_max=100,
        claim_fine_split_early_stop_after_blocks=0,
        claim_fine_split_min_hit_blocks_to_continue=0,
    )

    with pytest.raises(KnowledgeSourceNotFound):
        parser.parse_source("missing")


def test_knowledge_feedback_service_raises_module_validation_error() -> None:
    service = KnowledgeFeedbackService(
        source_store=SimpleNamespace(get=lambda _source_id: None),
        load_existing_global_profiles=lambda **_kwargs: [],
        log_step=lambda *_args, **_kwargs: None,
    )

    with pytest.raises(KnowledgeValidationError):
        service.apply(
            tenant="tenant",
            corpus_uuid="kb-1",
            target_entity="Entity",
            claim_text="Claim",
            feedback_type="unsupported",
        )
    with pytest.raises(KnowledgeValidationError):
        service.withdraw_source(tenant="tenant", corpus_uuid="kb-1", source_id="")


def test_knowledge_lineage_service_raises_module_validation_error() -> None:
    service = KnowledgeLineageService(SimpleNamespace())

    with pytest.raises(KnowledgeValidationError):
        service.get_lineage(corpus_uuid="kb-1")


def test_knowledge_source_unavailable_is_module_app_error() -> None:
    with pytest.raises(KnowledgeSourceUnavailable):
        raise KnowledgeSourceUnavailable("No extractable text.")
