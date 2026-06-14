from __future__ import annotations

from fastapi import Request

from apps.kb.kb_search.bootstrap.service_keys import KB_SEARCH_PIPELINE
from core.kernel.http.app_dependencies import get_module_service


def get_kb_search_pipeline(request: Request):
    return get_module_service(KB_SEARCH_PIPELINE, request)


__all__ = ["get_kb_search_pipeline"]
