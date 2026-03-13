from abc import ABC, abstractmethod
from typing import List, Optional, Tuple
from apps.knowledge.domain.kb import KnowledgeBase

# user_id -> permission: 'use' | 'train'
KbPermissionItem = Tuple[int, str]


class KnowledgeBaseRepositoryPort(ABC):

    @abstractmethod
    def list_all(self) -> List[KnowledgeBase]:
        ...

    @abstractmethod
    def get_by_uuid(self, uuid: str) -> Optional[KnowledgeBase]:
        ...

    @abstractmethod
    def get_by_id(self, kb_id: int) -> Optional[KnowledgeBase]:
        ...

    @abstractmethod
    def get_by_name(self, name: str) -> Optional[KnowledgeBase]:
        ...

    @abstractmethod
    def create(self, kb: KnowledgeBase) -> KnowledgeBase:
        ...

    @abstractmethod
    def update(self, kb: KnowledgeBase) -> KnowledgeBase:
        ...

    @abstractmethod
    def delete(self, uuid: str) -> None:
        ...

    @abstractmethod
    def list_permissions(self, kb_uuid: str) -> List[KbPermissionItem]:
        """(user_id, permission) list for this KB."""
        ...

    @abstractmethod
    def set_permissions(self, kb_uuid: str, permissions: List[KbPermissionItem]) -> None:
        """Replace all permissions for this KB. permission 'none' means omit (no row)."""
        ...

    @abstractmethod
    def get_kb_ids_with_permission(self, user_id: int, permission: str) -> List[int]:
        """KB id-k where user has this permission (or higher: train implies use)."""
        ...

    # --- Tanítási napló ---
    @abstractmethod
    def add_training_log(
        self,
        kb_id: int,
        point_id: str,
        user_id: Optional[int],
        user_display: Optional[str],
        title: str,
        content: Optional[str],
    ) -> None:
        """Tanítási naplóbejegyzés hozzáadása (add_block után). user_display = név vagy email."""
        ...

    @abstractmethod
    def list_training_log(self, kb_uuid: str) -> List[dict]:
        """Tanítási napló listája: user name/email, title, content, created_at, point_id. Legújabb elől."""
        ...

    @abstractmethod
    def delete_training_log_by_point_id(self, kb_id: int, point_id: str) -> bool:
        """Törlés point_id alapján. True ha töröltünk."""
        ...

    @abstractmethod
    def add_personal_data(self, kb_id: int, data_type: str, extracted_value: str) -> str:
        """Kiszűrt személyes adat tárolása; visszaadja a reference_id-t (a [típus_reference_id] helyettesítőhöz)."""
        ...
