from __future__ import annotations

from typing import Any

from apps.knowledge.domain.ingest_item import IngestItem
from apps.knowledge.service.ingest_progress_service import IngestProgressService


class IngestPipelineProgressService:
    def __init__(self, *, progress_service: IngestProgressService) -> None:
        self._progress = progress_service
        self._current_item: IngestItem | None = None

    def callback_for(self, item: IngestItem):
        self._current_item = item

        def _pipeline_progress(stage: str, payload: dict[str, Any]) -> None:
            self.handle(stage, payload)

        return _pipeline_progress

    @property
    def current_item(self) -> IngestItem:
        if self._current_item is None:
            raise RuntimeError("Pipeline progress callback was used before initialization.")
        return self._current_item

    def handle(self, stage: str, payload: dict[str, Any]) -> None:
        if stage in {"parser_block_started", "parser_block_units_ready", "parser_block_completed"}:
            self._handle_parser_block_progress(stage, payload)
            return
        handler = self._handler_for(stage)
        if handler is None:
            return
        handler(payload)

    def _handler_for(self, stage: str):
        handlers = {
            "file_character_count_started": self._handle_file_character_count_started,
            "file_bytes_loaded": self._handle_file_bytes_loaded,
            "file_character_count_completed": self._handle_file_character_count_completed,
            "parser_started": self._handle_parser_started,
            "parser_completed": self._handle_parser_completed,
            "parser_failed": self._handle_parser_failed,
            "interpretation_started": self._handle_interpretation_started,
            "interpretation_progress": self._handle_interpretation_progress,
            "interpretation_completed": self._handle_interpretation_completed,
            "interpretation_failed": self._handle_interpretation_failed,
            "interpretation_skipped": self._handle_interpretation_skipped,
        }
        return handlers.get(stage)

    def _handle_file_character_count_started(self, payload: dict[str, Any]) -> None:
        size_bytes = int(payload.get("size_bytes") or 0)
        estimated_char_count = int(payload.get("estimated_char_count") or 0)
        label = (
            f"Fájl beolvasása és karakterszám becslése indul "
            f"({self._progress.format_size_label(size_bytes)}, kb. {estimated_char_count} karakter)."
        )
        self._current_item = self._progress.update_item_processing_summary(
            self._current_item,
            progress_message=label,
            module_updates={
                "parser": self._progress.build_processing_module(
                    key="parser",
                    status="processing",
                    label="Mondatkinyerés",
                    message=label,
                ),
            },
            document_progress=self._progress.build_document_progress(
                phase="file_character_count",
                processed_parts=max(1, int(max(size_bytes, 1) * 0.05)) if size_bytes > 0 else 0,
                total_parts=max(size_bytes, 1),
                label=label,
                extra={
                    "size_bytes": size_bytes,
                    "estimated_char_count": estimated_char_count,
                },
            ),
            extra_metadata={
                "size_bytes": size_bytes,
                "estimated_char_count": estimated_char_count,
            },
        )

    def _handle_file_bytes_loaded(self, payload: dict[str, Any]) -> None:
        size_bytes = int(payload.get("size_bytes") or 0)
        processed_bytes = int(payload.get("processed_bytes") or 0)
        estimated_char_count = int(payload.get("estimated_char_count") or 0)
        label = (
            f"Fájl beolvasva, szövegkinyerés és karakterszámolás folyamatban "
            f"({self._progress.format_size_label(size_bytes)}, kb. {estimated_char_count} karakter)."
        )
        # A szövegkinyerés nem minden formátumnál mérhető soronként, ezért a fájlméretből becsült köztes állapotot mutatjuk.
        estimated_processed = max(1, int(max(size_bytes, 1) * 0.7))
        self._current_item = self._progress.update_item_processing_summary(
            self._current_item,
            progress_message=label,
            module_updates={
                "parser": self._progress.build_processing_module(
                    key="parser",
                    status="processing",
                    label="Mondatkinyerés",
                    processed_parts=min(estimated_processed, max(size_bytes, 1)),
                    total_parts=max(size_bytes, 1),
                    message=label,
                ),
            },
            document_progress=self._progress.build_document_progress(
                phase="file_character_count",
                processed_parts=min(estimated_processed, max(size_bytes, 1)),
                total_parts=max(size_bytes, 1),
                label=label,
                extra={
                    "size_bytes": size_bytes,
                    "processed_bytes": processed_bytes,
                    "estimated_char_count": estimated_char_count,
                },
            ),
        )

    def _handle_file_character_count_completed(self, payload: dict[str, Any]) -> None:
        size_bytes = int(payload.get("size_bytes") or 0)
        estimated_char_count = int(payload.get("estimated_char_count") or 0)
        char_count = int(payload.get("char_count") or 0)
        paragraph_count = int(payload.get("paragraph_count") or 0)
        label = (
            f"Karakterszámolás kész: {char_count} karakter "
            f"({self._progress.format_size_label(size_bytes)}, becslés: {estimated_char_count})."
        )
        self._current_item = self._progress.update_item_processing_summary(
            self._current_item,
            progress_message=label,
            module_updates={
                "parser": self._progress.build_processing_module(
                    key="parser",
                    status="processing",
                    label="Mondatkinyerés",
                    processed_parts=max(size_bytes, 1),
                    total_parts=max(size_bytes, 1),
                    message=label,
                ),
            },
            document_progress=self._progress.build_document_progress(
                phase="file_character_count",
                processed_parts=max(size_bytes, 1),
                total_parts=max(size_bytes, 1),
                label=label,
                extra={
                    "size_bytes": size_bytes,
                    "estimated_char_count": estimated_char_count,
                    "char_count": char_count,
                    "paragraph_count": paragraph_count,
                },
            ),
            extra_metadata={
                "estimated_char_count": estimated_char_count,
                "char_count": char_count,
                "paragraph_count": paragraph_count,
            },
        )

    def _handle_parser_started(self, payload: dict[str, Any]) -> None:
        self._current_item = self._progress.update_item_processing_summary(
            self._current_item,
            progress_message="A parser modul fut, a dokumentum szerkezetét készíti elő.",
            module_updates={
                "parser": self._progress.build_processing_module(
                    key="parser",
                    status="processing",
                    label="Mondatkinyerés",
                    run_id=str(payload.get("parser_run_id") or ""),
                    message="A parser modul fut.",
                ),
            },
        )

    def _handle_parser_block_progress(self, stage: str, payload: dict[str, Any]) -> None:
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
        self._current_item = self._progress.update_item_processing_summary(
            self._current_item,
            progress_message=progress_message,
            module_updates={
                "parser": self._progress.build_processing_module(
                    key="parser",
                    status="processing",
                    label="Mondatkinyerés",
                    processed_parts=int(payload.get("blocks_completed") or 0),
                    total_parts=total_blocks,
                    run_id=str(payload.get("parser_run_id") or ""),
                    message=progress_message,
                ),
            },
            document_progress=self._progress.build_document_progress(
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

    def _handle_parser_completed(self, payload: dict[str, Any]) -> None:
        sentence_count = int(payload.get("sentence_count") or 0)
        self._current_item = self._progress.update_item_processing_summary(
            self._current_item,
            progress_message=f"A parser elkészült, {sentence_count} mondat azonosítva.",
            module_updates={
                "parser": self._progress.build_processing_module(
                    key="parser",
                    status="completed",
                    label="Mondatkinyerés",
                    processed_parts=sentence_count,
                    total_parts=sentence_count,
                    run_id=str(payload.get("parser_run_id") or ""),
                    message="A parser modul elkészült.",
                ),
                "sentence_interpretation": self._progress.build_processing_module(
                    key="sentence_interpretation",
                    status="queued",
                    label="Mondatértelmezés",
                    processed_parts=0,
                    total_parts=sentence_count,
                    message="A mondatok értelmezése indulásra kész.",
                ),
                "sentence_evaluation": self._progress.build_processing_module(
                    key="sentence_evaluation",
                    status="queued",
                    label="Mondatértékelés",
                    processed_parts=0,
                    total_parts=sentence_count,
                    message="A mondatok értékelése indulásra kész.",
                ),
            },
            document_progress=self._progress.build_document_progress(
                phase="sentence_interpretation",
                processed_parts=0,
                total_parts=sentence_count,
                label=f"0 / {sentence_count} mondat értelmezve",
            ),
            extra_metadata={
                "parser_run_id": payload.get("parser_run_id"),
                "document_id": payload.get("document_id"),
                "char_count": int(payload.get("char_count") or 0),
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

    def _handle_parser_failed(self, payload: dict[str, Any]) -> None:
        self._current_item = self._progress.update_item_processing_summary(
            self._current_item,
            progress_message="A parser modul hibára futott.",
            module_updates={
                "parser": self._progress.build_processing_module(
                    key="parser",
                    status="failed",
                    label="Mondatkinyerés",
                    run_id=str(payload.get("parser_run_id") or ""),
                    error_message=str(payload.get("error_message") or ""),
                ),
            },
        )

    def _handle_interpretation_started(self, payload: dict[str, Any]) -> None:
        total_sentences = int(payload.get("total_sentences") or 0)
        self._current_item = self._progress.update_item_processing_summary(
            self._current_item,
            progress_message="A mondatok értelmezése és értékelése folyamatban van.",
            module_updates={
                "sentence_interpretation": self._progress.build_processing_module(
                    key="sentence_interpretation",
                    status="processing",
                    label="Mondatértelmezés",
                    processed_parts=int(payload.get("processed_sentences") or 0),
                    total_parts=total_sentences,
                    run_id=str(payload.get("interpretation_run_id") or ""),
                    message="A mondatok értelmezése folyamatban van.",
                ),
                "sentence_evaluation": self._progress.build_processing_module(
                    key="sentence_evaluation",
                    status="processing",
                    label="Mondatértékelés",
                    processed_parts=int(payload.get("processed_sentences") or 0),
                    total_parts=total_sentences,
                    message="A mondatok információértékének meghatározása folyamatban van.",
                ),
            },
            document_progress=self._progress.build_document_progress(
                phase="sentence_interpretation",
                processed_parts=int(payload.get("processed_sentences") or 0),
                total_parts=total_sentences,
                label=f"0 / {total_sentences} mondat kész",
            ),
            extra_metadata={"interpretation_run_id": payload.get("interpretation_run_id")},
        )

    def _handle_interpretation_progress(self, payload: dict[str, Any]) -> None:
        processed_sentences = int(payload.get("processed_sentences") or 0)
        total_sentences = int(payload.get("total_sentences") or 0)
        self._current_item = self._progress.update_item_processing_summary(
            self._current_item,
            progress_message=f"Mondatfeldolgozás: {processed_sentences} / {total_sentences} kész.",
            module_updates={
                "sentence_interpretation": self._progress.build_processing_module(
                    key="sentence_interpretation",
                    status="processing",
                    label="Mondatértelmezés",
                    processed_parts=processed_sentences,
                    total_parts=total_sentences,
                    run_id=str(payload.get("interpretation_run_id") or ""),
                    message=f"{processed_sentences} / {total_sentences} mondat értelmezve.",
                ),
                "sentence_evaluation": self._progress.build_processing_module(
                    key="sentence_evaluation",
                    status="processing",
                    label="Mondatértékelés",
                    processed_parts=processed_sentences,
                    total_parts=total_sentences,
                    message=f"{processed_sentences} / {total_sentences} mondat értékelve.",
                ),
            },
            document_progress=self._progress.build_document_progress(
                phase="sentence_interpretation",
                processed_parts=processed_sentences,
                total_parts=total_sentences,
                label=f"{processed_sentences} / {total_sentences} mondat kész",
            ),
        )

    def _handle_interpretation_completed(self, payload: dict[str, Any]) -> None:
        processed_sentences = int(payload.get("processed_sentences") or 0)
        total_sentences = int(payload.get("total_sentences") or processed_sentences)
        quality = dict(payload.get("quality") or {})
        self._current_item = self._progress.update_item_processing_summary(
            self._current_item,
            progress_message=f"A mondatok értelmezése elkészült ({processed_sentences} / {total_sentences}).",
            module_updates={
                "sentence_interpretation": self._progress.build_processing_module(
                    key="sentence_interpretation",
                    status="completed",
                    label="Mondatértelmezés",
                    processed_parts=processed_sentences,
                    total_parts=total_sentences,
                    run_id=str(payload.get("interpretation_run_id") or ""),
                    message="A mondatok értelmezése elkészült.",
                ),
                "sentence_evaluation": self._progress.build_processing_module(
                    key="sentence_evaluation",
                    status="completed",
                    label="Mondatértékelés",
                    processed_parts=processed_sentences,
                    total_parts=total_sentences,
                    message="A mondatok információérték-értékelése elkészült.",
                ),
            },
            document_progress=self._progress.build_document_progress(
                phase="sentence_interpretation",
                processed_parts=processed_sentences,
                total_parts=total_sentences,
                label=f"{processed_sentences} / {total_sentences} mondat kész",
            ),
            extra_metadata={"interpretation_quality": quality},
        )

    def _handle_interpretation_failed(self, payload: dict[str, Any]) -> None:
        self._current_item = self._progress.update_item_processing_summary(
            self._current_item,
            progress_message="A mondatértelmezés hibára futott.",
            module_updates={
                "sentence_interpretation": self._progress.build_processing_module(
                    key="sentence_interpretation",
                    status="failed",
                    label="Mondatértelmezés",
                    processed_parts=int(payload.get("processed_sentences") or 0),
                    total_parts=int(payload.get("total_sentences") or 0),
                    run_id=str(payload.get("interpretation_run_id") or ""),
                    error_message=str(payload.get("error_message") or ""),
                ),
                "sentence_evaluation": self._progress.build_processing_module(
                    key="sentence_evaluation",
                    status="failed",
                    label="Mondatértékelés",
                    processed_parts=int(payload.get("processed_sentences") or 0),
                    total_parts=int(payload.get("total_sentences") or 0),
                    error_message=str(payload.get("error_message") or ""),
                ),
            },
        )

    def _handle_interpretation_skipped(self, payload: dict[str, Any]) -> None:
        total_sentences = int(payload.get("total_sentences") or 0)
        self._current_item = self._progress.update_item_processing_summary(
            self._current_item,
            progress_message="A mondatértelmezés ebben a környezetben ki lett hagyva.",
            module_updates={
                "sentence_interpretation": self._progress.build_processing_module(
                    key="sentence_interpretation",
                    status="skipped",
                    label="Mondatértelmezés",
                    processed_parts=0,
                    total_parts=total_sentences,
                    message=str(payload.get("reason") or "A modul nem elérhető."),
                ),
                "sentence_evaluation": self._progress.build_processing_module(
                    key="sentence_evaluation",
                    status="skipped",
                    label="Mondatértékelés",
                    processed_parts=0,
                    total_parts=total_sentences,
                    message=str(payload.get("reason") or "A modul nem elérhető."),
                ),
            },
            document_progress=self._progress.build_document_progress(
                phase="parser",
                processed_parts=total_sentences,
                total_parts=total_sentences,
                label="A parser elkészült, az értelmezés ki lett hagyva.",
            ),
        )




__all__ = ["IngestPipelineProgressService"]
