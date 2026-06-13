from __future__ import annotations

from fastapi import Request

from apps.kb.kb_discovery.bootstrap.service_keys import KB_DISCOVERY_JOB_REPOSITORY
from core.kernel.http.app_dependencies import get_module_repository


def get_discovery_job_repository(request: Request):
    return get_module_repository(KB_DISCOVERY_JOB_REPOSITORY, request)


__all__ = ["get_discovery_job_repository"]
