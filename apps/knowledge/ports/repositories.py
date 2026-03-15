from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, List, Optional, Tuple  # noqa: F401
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
        idempotency_key: Optional[str] = None,
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
    def get_training_log_by_idempotency_key(self, kb_id: int, idempotency_key: str) -> Optional[dict]:
        """Tanítási napló rekord lekérdezése idempotency kulcs alapján."""
        ...

    @abstractmethod
    def get_training_log_entry(self, kb_id: int, point_id: str) -> Optional[dict]:
        """Egy tanítási napló sor lekérdezése point_id alapján."""
        ...

    @abstractmethod
    def enqueue_vector_outbox(
        self,
        kb_id: int,
        operation_type: str,
        payload: dict,
        source_point_id: Optional[str] = None,
    ) -> int:
        """Vector outbox rekord létrehozása. Visszatér: outbox id."""
        ...

    @abstractmethod
    def list_due_vector_outbox(self, limit: int = 50) -> List[dict]:
        """Feldolgozásra kész (pending/failed) outbox elemek listája."""
        ...

    @abstractmethod
    def mark_vector_outbox_done(self, outbox_id: int) -> None:
        """Outbox elem készre állítása."""
        ...

    @abstractmethod
    def mark_vector_outbox_retry(self, outbox_id: int, error: str, backoff_seconds: int) -> None:
        """Outbox elem retry-re állítása hibával és következő időponttal."""
        ...

    @abstractmethod
    def get_vector_outbox_stats(self, kb_id: Optional[int] = None, recent_limit: int = 20) -> dict:
        """Outbox statisztikák és legutóbbi elemek dashboardhoz."""
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

    # --- Retrieval/indexing derived adatok ---
    @abstractmethod
    def create_sentence_batch(self, kb_id: int, source_point_id: str, rows: List[dict]) -> List[dict]:
        """Mondat rekordok tömeges mentése; visszaadja létrehozott sorokat id-vel."""
        ...

    @abstractmethod
    def create_structural_chunk_batch(self, kb_id: int, source_point_id: str, rows: List[dict]) -> List[dict]:
        """Chunk rekordok tömeges mentése; visszaadja létrehozott sorokat id-vel."""
        ...

    @abstractmethod
    def create_mentions_batch(self, sentence_id: int, rows: List[dict]) -> List[dict]:
        """Mention rekordok tömeges mentése mondathoz."""
        ...

    @abstractmethod
    def update_sentence_enrichment_batch(self, kb_id: int, rows: List[dict]) -> int:
        """Sentence enrichment meta frissítése tömegesen."""
        ...

    @abstractmethod
    def update_structural_chunk_enrichment_batch(self, kb_id: int, rows: List[dict]) -> int:
        """Chunk enrichment meta frissítése tömegesen."""
        ...

    @abstractmethod
    def upsert_entity(self, kb_id: int, payload: dict) -> dict:
        """Entitás upsert canonical név alapján."""
        ...

    @abstractmethod
    def upsert_time_interval(self, kb_id: int, payload: dict) -> dict:
        """Időintervallum upsert normalizált kulcs alapján."""
        ...

    @abstractmethod
    def upsert_place(self, kb_id: int, payload: dict) -> dict:
        """Hely upsert normalizált kulcs alapján."""
        ...

    @abstractmethod
    def upsert_assertion(self, kb_id: int, payload: dict) -> dict:
        """Assertion upsert fingerprint alapján."""
        ...

    @abstractmethod
    def add_assertion_evidence(
        self,
        kb_id: int,
        assertion_id: int,
        sentence_id: int,
        source_point_id: str,
        evidence_type: str = "PRIMARY",
        confidence: float | None = None,
        weight: float = 1.0,
    ) -> None:
        """Assertion–evidence kapcsolat rögzítése."""
        ...

    @abstractmethod
    def add_reinforcement_event(
        self,
        kb_id: int,
        target_type: str,
        target_id: int,
        event_type: str,
        weight: float = 1.0,
    ) -> None:
        """Erősítési esemény mentése."""
        ...

    @abstractmethod
    def add_assertion_relation(
        self,
        kb_id: int,
        from_assertion_id: int,
        to_assertion_id: int,
        relation_type: str,
        weight: float = 1.0,
        relation_confidence: float | None = None,
    ) -> None:
        """Assertion kapcsolati él mentése."""
        ...

    @abstractmethod
    def create_assertion_relations_batch(self, kb_id: int, rows: List[dict]) -> int:
        """Assertion kapcsolatok tömeges mentése."""
        ...

    @abstractmethod
    def list_assertions_by_source_point_id(self, kb_id: int, source_point_id: str) -> List[dict]:
        """Assertion lista source_point szerint."""
        ...

    @abstractmethod
    def list_mentions_for_assertion(self, assertion_id: int) -> List[dict]:
        """Assertionhöz tartozó mondat mention listája."""
        ...

    @abstractmethod
    def list_sentences_by_source_point_id(self, kb_id: int, source_point_id: str) -> List[dict]:
        """Sentence lista source_point szerint."""
        ...

    @abstractmethod
    def list_chunks_by_source_point_id(self, kb_id: int, source_point_id: str) -> List[dict]:
        """Chunk lista source_point szerint."""
        ...

    @abstractmethod
    def list_assertion_evidence(self, assertion_id: int) -> List[dict]:
        """Assertion evidence rekordok listája."""
        ...

    @abstractmethod
    def list_assertion_relations(self, assertion_ids: List[int], limit: int = 200) -> List[dict]:
        """Assertion kapcsolatok listázása assertion id-k körül."""
        ...

    @abstractmethod
    def get_assertion_neighbors(
        self,
        kb_id: int,
        assertion_ids: List[int],
        max_hops: int = 1,
        allowed_relation_types: Optional[List[str]] = None,
        limit: int = 80,
    ) -> List[dict]:
        """Szomszéd assertionök lekérdezése relation hálón."""
        ...

    @abstractmethod
    def list_evidence_sentences(self, assertion_ids: List[int], limit: int = 50) -> List[dict]:
        """Assertionökhöz kapcsolt bizonyító mondatok."""
        ...

    @abstractmethod
    def list_chunks_for_sentence_ids(self, sentence_ids: List[int], limit: int = 30) -> List[dict]:
        """Mondatokhoz tartozó forrás chunkok listája."""
        ...

    @abstractmethod
    def delete_derived_records_by_source_point_id(self, kb_id: int, source_point_id: str) -> int:
        """Derived rekordok törlése source_point szerint. Visszatér: törölt sorok becsült száma."""
        ...

    @abstractmethod
    def search_candidate_assertions(
        self,
        kb_ids: List[int],
        predicates: Optional[List[str]] = None,
        entity_ids: Optional[List[int]] = None,
        limit: int = 50,
    ) -> List[dict]:
        """Assertion seed lekérdezés context építéshez."""
        ...

    @abstractmethod
    def search_assertion_candidates(
        self,
        kb_ids: List[int],
        predicates: Optional[List[str]] = None,
        entity_ids: Optional[List[int]] = None,
        limit: int = 50,
    ) -> List[dict]:
        """Alias: assertion seed lekérdezés context építéshez."""
        ...

    @abstractmethod
    def search_entity_candidates(self, kb_ids: List[int], query: str, limit: int = 20) -> List[dict]:
        """Entitás jelölt keresés canonical/alias alapján."""
        ...

    @abstractmethod
    def merge_entities(self, kb_id: int, source_entity_id: int, target_entity_id: int) -> bool:
        """Két entitás összevonása target irányba."""
        ...

    @abstractmethod
    def get_entities_by_ids(self, kb_id: int, entity_ids: List[int]) -> List[dict]:
        """Entitások lekérése id lista alapján."""
        ...

    @abstractmethod
    def get_allowed_kb_ids_for_user(self, user_id: int) -> List[int]:
        """Felhasználó által használható KB-k id listája."""
        ...

    @abstractmethod
    def get_assertion_by_id(self, kb_id: int, assertion_id: int) -> Optional[dict]:
        """Assertion lekérdezése id alapján."""
        ...

    @abstractmethod
    def update_assertion_strength(
        self,
        kb_id: int,
        assertion_id: int,
        strength: float,
        last_reinforced_at: Optional[datetime] = None,
        reinforcement_increment: int = 0,
    ) -> bool:
        """Assertion strength frissítése."""
        ...

    @abstractmethod
    def update_assertion_status(self, kb_id: int, assertion_id: int, status: str) -> bool:
        """Assertion státusz frissítése."""
        ...

    @abstractmethod
    def list_assertions_for_kb(self, kb_id: int, limit: int = 1000, offset: int = 0) -> List[dict]:
        """Assertion lista egy KB-hoz decay/reindex feladatokhoz."""
        ...

    @abstractmethod
    def get_assertion_debug(self, kb_id: int, assertion_id: int) -> dict:
        """Assertion debug nézet: assertion + evidence + relations."""
        ...

    @abstractmethod
    def get_entity_debug(self, kb_id: int, entity_id: int) -> dict:
        """Entity debug nézet."""
        ...

    @abstractmethod
    def get_source_point_debug(self, kb_id: int, source_point_id: str) -> dict:
        """Source point debug nézet."""
        ...

    @abstractmethod
    def get_relation_bundle(self, kb_id: int, assertion_id: int, limit: int = 60) -> dict:
        """Assertion relation bundle lekérése."""
        ...

    @abstractmethod
    def get_metric_snapshot(self, kb_id: int) -> dict:
        """Retrieval minőség- és állapot snapshot metrikák."""
        ...
