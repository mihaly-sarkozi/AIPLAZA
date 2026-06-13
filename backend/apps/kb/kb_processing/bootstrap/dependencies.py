from __future__ import annotations

from apps.kb.kb_processing.bootstrap.service_keys import KB_PROCESSING_STATUS_SERVICE
from apps.kb.kb_processing.service.ProcessingStatusService import ProcessingStatusService
from core.kernel.http.app_dependencies import get_module_service
from core.modules.auth.web.dependencies.auth_dependencies import require_permission
from fastapi import Request

require_kb_read = require_permission("kb.read")


def get_processing_status_service(request: Request) -> ProcessingStatusService:
    return get_module_service(KB_PROCESSING_STATUS_SERVICE, request)


__all__ = ["get_processing_status_service", "require_kb_read"]
