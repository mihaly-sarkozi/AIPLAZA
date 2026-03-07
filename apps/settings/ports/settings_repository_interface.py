# apps/settings/ports/settings_repository_interface.py
# Rendszer beállítások repository interface
# 2026.03.07 - Sárközi Mihály

from abc import ABC, abstractmethod
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from apps.settings.domain.setting import Setting


class SettingsRepositoryInterface(ABC):
    @abstractmethod
    def get_by_key(self, key: str) -> Optional["Setting"]:
        ...

    @abstractmethod
    def create_or_update(self, setting: "Setting") -> "Setting":
        ...
