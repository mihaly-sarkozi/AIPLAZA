from __future__ import annotations

from core.kernel.http.app_errors import AppError


class KnowledgeError(AppError):
    code = "KNOWLEDGE_ERROR"
    status_code = 500
    safe_message = "Knowledge operation failed."


class KnowledgePermissionDenied(KnowledgeError):
    code = "KNOWLEDGE_PERMISSION_DENIED"
    status_code = 403
    safe_message = "No permission to access this knowledge resource."


class KnowledgeBaseNotFound(KnowledgeError):
    code = "KNOWLEDGE_BASE_NOT_FOUND"
    status_code = 404
    safe_message = "Knowledge base not found."


class KnowledgeValidationError(KnowledgeError):
    code = "KNOWLEDGE_VALIDATION_ERROR"
    status_code = 400
    safe_message = "Invalid knowledge request."


class IngestRunNotFound(KnowledgeError):
    code = "INGEST_RUN_NOT_FOUND"
    status_code = 404
    safe_message = "Ingest run not found."


class IngestItemNotFound(KnowledgeError):
    code = "INGEST_ITEM_NOT_FOUND"
    status_code = 404
    safe_message = "Ingest item not found."


class IngestItemReprocessConflict(KnowledgeError):
    code = "INGEST_ITEM_REPROCESS_CONFLICT"
    status_code = 409
    safe_message = "Ingest item cannot be reprocessed right now."


class IngestInputNotFound(KnowledgeError):
    code = "INGEST_INPUT_NOT_FOUND"
    status_code = 404
    safe_message = "Ingest input not found."


class IngestQueueUnavailable(KnowledgeError):
    code = "INGEST_QUEUE_UNAVAILABLE"
    status_code = 503
    safe_message = "Ingest queue is unavailable."


__all__ = [
    "IngestInputNotFound",
    "IngestItemNotFound",
    "IngestItemReprocessConflict",
    "IngestQueueUnavailable",
    "IngestRunNotFound",
    "KnowledgeBaseNotFound",
    "KnowledgeError",
    "KnowledgePermissionDenied",
    "KnowledgeValidationError",
]
