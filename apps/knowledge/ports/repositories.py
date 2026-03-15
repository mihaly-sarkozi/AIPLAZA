from abc import ABC, abstractmethod
from typing import List, Optional, Tuple  # noqa: F401
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
    def list_permissions_batch(self, kb_uuids: List[str]) -> dict[str, List[KbPermissionItem]]:
        """KB UUID -> (user_id, permission) list map."""
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
        raw_content: Optional[str] = None,
        review_decision: Optional[str] = None,
    ) -> None:
        """Tanítási naplóbejegyzés hozzáadása. content = sanitized; raw_content/review_decision optional (PII review flow)."""
        ...

    @abstractmethod
    def list_training_log(self, kb_uuid: str) -> List[dict]:
        """Tanítási napló listája: user name/email, title, content, created_at, point_id. Legújabb elől."""
        ...
    
    @abstractmethod
    def list_training_log_paginated(
        self,
        kb_uuid: str,
        limit: int = 50,
        offset: int = 0,
        include_raw_content: bool = False,
    ) -> List[dict]:
        """Tanítási napló lapozva; nyers tartalom csak explicit kérésre."""
        ...

    @abstractmethod
    def delete_training_log_by_point_id(self, kb_id: int, point_id: str) -> bool:
        """Törlés point_id alapján. True ha töröltünk."""
        ...

    @abstractmethod
    def add_personal_data(
        self, kb_id: int, point_id: str, data_type: str, extracted_value: str
    ) -> str:
        """Kiszűrt személyes adat tárolása; visszaadja a reference_id-t (a [típus_reference_id] helyettesítőhöz)."""
        ...

    @abstractmethod
    def list_personal_data_by_point_id(self, kb_id: int, point_id: str) -> List[Tuple[str, str]]:
        """point_id-hez tartozó személyes adatok: [(reference_id, extracted_value), ...]."""
        ...

    @abstractmethod
    def purge_expired_personal_data(self) -> int:
        """Lejárt személyes adatok törlése. Visszatér: törölt rekordok száma."""
        ...

    @abstractmethod
    def list_personal_data_records(self, kb_id: int, limit: int = 1000, offset: int = 0) -> List[dict]:
        """PII rekordok listája decryptelve (reference_id, point_id, data_type, value, created_at, expires_at)."""
        ...

    @abstractmethod
    def delete_personal_data_by_reference_ids(self, kb_id: int, reference_ids: List[str]) -> int:
        """PII rekordok törlése referencia azonosítók alapján. Visszatér: törölt sorok száma."""
        ...

    @abstractmethod
    def personal_data_metrics(self, kb_id: int) -> dict:
        """PII metrikák adott KB-ra (total, expired, by_type)."""
        ...
