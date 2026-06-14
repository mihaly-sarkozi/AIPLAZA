from __future__ import annotations

from apps.kb.kb_indexing.bootstrap.service_keys import KB_INDEXING_DIAGNOSTICS_SERVICE
from apps.kb.kb_indexing.service.IndexingDiagnosticsService import IndexingDiagnosticsService
from core.kernel.http.app_dependencies import get_module_service
from core.modules.auth.web.dependencies.auth_dependencies import require_permission
from fastapi import Request

require_kb_admin = require_permission("kb.admin")


def get_indexing_diagnostics_service(request: Request) -> IndexingDiagnosticsService:
    return get_module_service(KB_INDEXING_DIAGNOSTICS_SERVICE, request)


__all__ = ["get_indexing_diagnostics_service", "require_kb_admin"]
