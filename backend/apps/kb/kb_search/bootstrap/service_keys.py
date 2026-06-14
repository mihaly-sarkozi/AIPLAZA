from __future__ import annotations

from core.kernel.interface.app_keys import module_service_key

KB_SEARCH_CHAT_FACADE = module_service_key("kb", "search.chat_facade")
KB_SEARCH_PIPELINE = module_service_key("kb", "search.pipeline")
KB_SEARCH_RUN_REPOSITORY = module_service_key("kb", "search.run_repository")

__all__ = [
    "KB_SEARCH_CHAT_FACADE",
    "KB_SEARCH_PIPELINE",
    "KB_SEARCH_RUN_REPOSITORY",
]
