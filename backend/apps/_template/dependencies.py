from __future__ import annotations

from apps._template.contracts import TEMPLATE_SERVICE
from apps.di import module_service_dependency

get_template_service = module_service_dependency(TEMPLATE_SERVICE)

__all__ = ["get_template_service"]
