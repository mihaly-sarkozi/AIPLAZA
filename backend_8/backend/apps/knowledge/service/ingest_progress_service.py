# backend/apps/knowledge/service/ingest_progress_service.py
# Builds and persists ingest progress summaries for runs and items.

from __future__ import annotations

import logging
from dataclasses import replace
from typing import Any, Callable

from apps.knowledge.domain.ingest_item import IngestItem
from apps.knowledge.domain.ingest_run import IngestRun
from apps.knowledge.service.facade_helpers import utcnow as _utcnow
from apps.knowledge.service.ports import IngestItemStorePort

logger = logging.getLogger(__name__)


class IngestProgressService:
    def __init__(
        self,
        *,
        ingest_item_store: IngestItemStorePort,
        refresh_ingest_run: Callable[[str], IngestRun],
    ) -> None:
        self._ingest_item_store = ingest_item_store
        self._refresh_ingest_run = refresh_ingest_run

    @staticmethod
    def compute_progress_percent(processed_parts: int | None, total_parts: int | None) -> int | None:
        if processed_parts is None or total_parts is None or total_parts <= 0:
            return None
        return max(0, min(100, int(round((processed_parts / total_parts) * 100))))

    @staticmethod
    def estimate_file_character_count_from_size(size_bytes: int | None) -> int:
        if size_bytes is None or size_bytes <= 0:
            return 0
        return max(1, int(round(size_bytes * 0.1)))

    @staticmethod
    def format_size_label(size_bytes: int | None) -> str:
        value = max(0, int(size_bytes or 0))
        if value >= 1024 * 1024:
            return f"{value / (1024 * 1024):.1f} MB"
        if value >= 1024:
            return f"{value / 1024:.1f} KB"
        return f"{value} B"

    @classmethod
    def build_processing_module(
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
            "progress_percent": cls.compute_progress_percent(processed_parts, total_parts),
        }
        if run_id:
            payload["run_id"] = run_id
        if message:
            payload["message"] = message
        if error_message:
            payload["error_message"] = error_message
        return payload

    @classmethod
    def build_document_progress(
        cls,
        *,
        phase: str,
        processed_parts: int | None,
        total_parts: int | None,
        label: str,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload = {
            "phase": phase,
            "processed_parts": processed_parts,
            "total_parts": total_parts,
            "progress_percent": cls.compute_progress_percent(processed_parts, total_parts),
            "label": label,
        }
        if extra:
            payload.update(extra)
        return payload

    @classmethod
    def compute_item_progress_percent(cls, item: IngestItem) -> int | None:
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
                if phase == "file_character_count":
                    progress_percent = document_progress.get("progress_percent")
                    if isinstance(progress_percent, (int, float)) and progress_percent > 0:
                        return max(8, min(20, int(round(progress_percent * 0.2))))
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
    def build_run_summary(cls, run: IngestRun, items: list[IngestItem]) -> dict[str, Any]:
        total_items = max(len(items), 1)
        terminal_items = sum(1 for item in items if item.status in {"completed", "failed", "duplicate", "rejected"})
        item_progress_total = sum(cls.compute_item_progress_percent(item) or 0 for item in items)
        overall_percent = max(0, min(100, int(round(item_progress_total / total_items)))) if items else 0
        if run.status in {"received", "queued", "processing"}:
            overall_percent = min(overall_percent, 99)

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
            "index_progress_state": str((run.metadata or {}).get("index_progress_state") or ""),
        }

    def update_item_processing_summary(
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
        updated = self._ingest_item_store.update(
            replace(
                item,
                progress_message=progress_message if progress_message is not None else item.progress_message,
                updated_at=_utcnow(),
                metadata=metadata,
            )
        )
        try:
            self._refresh_ingest_run(updated.ingest_run_id)
        except Exception:
            logger.debug("ingest run progress refresh failed", exc_info=True)
        return updated


__all__ = ["IngestProgressService"]
