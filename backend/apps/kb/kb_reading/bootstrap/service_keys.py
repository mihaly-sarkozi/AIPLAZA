from __future__ import annotations

# backend/apps/kb/kb_reading/bootstrap/service_keys.py
# Feladat: Szolgáltatás kulcsok a tároló regisztrációhoz.
# Sárközi Mihály - 2026.06.07

from core.kernel.interface.app_keys import module_service_key

KB_READING_REPOSITORY = module_service_key("kb", "reading.repository")
KB_READING_STORAGE = module_service_key("kb", "reading.storage")
KB_READING_EVENT_PUBLISHER = module_service_key("kb", "reading.event_publisher")
KB_READING_POLICY = module_service_key("kb", "reading.policy")

__all__ = [
    "KB_READING_EVENT_PUBLISHER",
    "KB_READING_POLICY",
    "KB_READING_REPOSITORY",
    "KB_READING_STORAGE",
]
