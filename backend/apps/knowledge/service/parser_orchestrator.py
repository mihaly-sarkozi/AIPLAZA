# backend/apps/knowledge/service/parser_orchestrator.py
# Feladat: Source parser futtatas, parser status/error mapping, valamint a
# document/paragraph/sentence rekordok eloallitasa. A KnowledgeFacade innen mar
# csak kompatibilitasi delegaciot tart fenn.

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import replace
from typing import Any

from apps.knowledge.domain.document import Document
from apps.knowledge.domain.paragraph import Paragraph
from apps.knowledge.domain.parser_run import ParserRun
from apps.knowledge.domain.sentence import Sentence
from apps.knowledge.domain.source import Source
from apps.knowledge.service.facade_helpers import utcnow as _utcnow
from apps.knowledge.service.language_rules import detect_language
from apps.knowledge.service.ports import (
    DocumentStorePort,
    ParagraphStorePort,
    ParserRunStorePort,
    SentenceStorePort,
    SourceStorePort,
)
from shared.documents import ExtractedParagraph

logger = logging.getLogger(__name__)


class ParserOrchestrator:
    def __init__(
        self,
        *,
        source_store: SourceStorePort,
        parser_run_store: ParserRunStorePort,
        document_store: DocumentStorePort,
        paragraph_store: ParagraphStorePort,
        sentence_store: SentenceStorePort,
        extract_parser_document_from_source: Callable[..., Any],
        delete_source_parse_outputs: Callable[[str], None],
        normalize_parser_text: Callable[[str | None], str],
        describe_empty_extraction: Callable[[dict[str, Any] | None], str],
        split_paragraphs: Callable[[str], list[str]],
        build_claim_refinement_budget: Callable[[int], int],
        build_sentence_units_for_paragraph_with_diagnostics: Callable[..., tuple[list[dict[str, Any]], dict[str, Any]]],
        interpret_document: Callable[..., Any],
        truncate_error_message: Callable[..., str],
        log_step: Callable[..., None],
        parser_error_message_max: int,
        claim_fine_split_early_stop_after_blocks: int,
        claim_fine_split_min_hit_blocks_to_continue: int,
    ) -> None:
        self._source_store = source_store
        self._parser_run_store = parser_run_store
        self._document_store = document_store
        self._paragraph_store = paragraph_store
        self._sentence_store = sentence_store
        self._extract_parser_document_from_source = extract_parser_document_from_source
        self._delete_source_parse_outputs = delete_source_parse_outputs
        self._normalize_parser_text = normalize_parser_text
        self._describe_empty_extraction = describe_empty_extraction
        self._split_paragraphs = split_paragraphs
        self._build_claim_refinement_budget = build_claim_refinement_budget
        self._build_sentence_units_for_paragraph_with_diagnostics = build_sentence_units_for_paragraph_with_diagnostics
        self._interpret_document = interpret_document
        self._truncate_error_message = truncate_error_message
        self._log_step = log_step
        self._parser_error_message_max = parser_error_message_max
        self._claim_fine_split_early_stop_after_blocks = claim_fine_split_early_stop_after_blocks
        self._claim_fine_split_min_hit_blocks_to_continue = claim_fine_split_min_hit_blocks_to_continue

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
            extracted_document = self._extract_parser_document_from_source(
                source,
                progress_callback=progress_callback,
            )
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
                "early_stop_after_blocks": self._claim_fine_split_early_stop_after_blocks,
                "min_hit_blocks_to_continue": self._claim_fine_split_min_hit_blocks_to_continue,
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
                        "char_count": document.char_count,
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
                        max_length=self._parser_error_message_max,
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


__all__ = ["ParserOrchestrator"]
