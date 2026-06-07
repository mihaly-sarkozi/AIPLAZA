from __future__ import annotations

# backend/apps/kb/kb_training/bootstrap/service_keys.py
# Feladat: Tanítási modul DI service kulcsok.
# Sárközi Mihály - 2026.06.07

from core.kernel.interface.app_keys import module_service_key

KB_TRAINING_REPOSITORY = module_service_key("kb", "training.repository")
KB_TRAINING_STORAGE = module_service_key("kb", "training.storage")

__all__ = [
    "KB_TRAINING_REPOSITORY",
    "KB_TRAINING_STORAGE",
]
