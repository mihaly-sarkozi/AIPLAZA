from abc import ABC, abstractmethod
from typing import List, Optional
from apps.knowledge.domain.kb import KnowledgeBase

class KnowledgeBaseRepositoryPort(ABC):

    @abstractmethod
    def list_all(self) -> List[KnowledgeBase]:
        ...

    @abstractmethod
    def get_by_uuid(self, uuid: str) -> Optional[KnowledgeBase]:
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
