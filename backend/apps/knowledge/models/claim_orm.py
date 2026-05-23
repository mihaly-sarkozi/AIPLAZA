from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB

from .base import TenantSchemaBase
from .utils import _utcnow_naive


class KnowledgeClaimORM(TenantSchemaBase):
    __tablename__ = "knowledge_claims"

    id = Column(String(36), primary_key=True)
    corpus_uuid = Column(String(36), nullable=False, index=True)
    source_id = Column(String(36), ForeignKey("knowledge_sources.id", ondelete="CASCADE"), nullable=False, index=True)
    document_id = Column(String(36), nullable=False, index=True)
    sentence_id = Column(String(36), ForeignKey("knowledge_sentences.id", ondelete="CASCADE"), nullable=False, index=True)
    interpretation_run_id = Column(String(36), nullable=False, index=True)
    subject_text = Column(Text, nullable=False, default="")
    predicate_text = Column(Text, nullable=False, default="")
    object_text = Column(Text, nullable=True)
    claim_type = Column(String(32), nullable=False, default="other", index=True)
    assertion_mode = Column(String(32), nullable=False, default="fact", index=True)
    time_mode = Column(String(32), nullable=False, default="unknown", index=True)
    time_label = Column(String(128), nullable=True)
    space_mode = Column(String(32), nullable=False, default="unknown", index=True)
    space_label = Column(String(128), nullable=True)
    confidence = Column(Float, nullable=False, default=0.5)
    metadata_json = Column("metadata", JSONB, nullable=False, default=dict)
    created_at = Column(DateTime, default=_utcnow_naive, nullable=False)

    @property
    def claim_id(self) -> str:
        return self.id

    @claim_id.setter
    def claim_id(self, value: str) -> None:
        self.id = value

    @property
    def predicate(self) -> str:
        return self.predicate_text

    @predicate.setter
    def predicate(self, value: str) -> None:
        self.predicate_text = value

    @property
    def claim_text(self) -> str:
        return " ".join(part for part in [self.subject_text, self.predicate_text, self.object_text] if part).strip()

    @claim_text.setter
    def claim_text(self, value: str) -> None:
        metadata = dict(self.metadata_json or {})
        metadata["claim_text"] = value
        self.metadata_json = metadata

    @property
    def claim_group(self) -> str:
        return str((self.metadata_json or {}).get("claim_group") or "default")

    @claim_group.setter
    def claim_group(self, value: str) -> None:
        metadata = dict(self.metadata_json or {})
        metadata["claim_group"] = value
        self.metadata_json = metadata

    @property
    def claim_status(self) -> str:
        return str((self.metadata_json or {}).get("claim_status") or "active")

    @claim_status.setter
    def claim_status(self, value: str) -> None:
        metadata = dict(self.metadata_json or {})
        metadata["claim_status"] = value
        self.metadata_json = metadata

    @property
    def subject_mention_id(self) -> str | None:
        value = (self.metadata_json or {}).get("subject_mention_id")
        return str(value) if value else None

    @subject_mention_id.setter
    def subject_mention_id(self, value: str | None) -> None:
        metadata = dict(self.metadata_json or {})
        metadata["subject_mention_id"] = value
        self.metadata_json = metadata

    @property
    def object_mention_id(self) -> str | None:
        value = (self.metadata_json or {}).get("object_mention_id")
        return str(value) if value else None

    @object_mention_id.setter
    def object_mention_id(self, value: str | None) -> None:
        metadata = dict(self.metadata_json or {})
        metadata["object_mention_id"] = value
        self.metadata_json = metadata

    @property
    def identity_weight(self) -> float:
        return float((self.metadata_json or {}).get("identity_weight") or 0.0)

    @identity_weight.setter
    def identity_weight(self, value: float) -> None:
        metadata = dict(self.metadata_json or {})
        metadata["identity_weight"] = float(value)
        self.metadata_json = metadata

    @property
    def similarity_weight(self) -> float:
        return float((self.metadata_json or {}).get("similarity_weight") or 1.0)

    @similarity_weight.setter
    def similarity_weight(self, value: float) -> None:
        metadata = dict(self.metadata_json or {})
        metadata["similarity_weight"] = float(value)
        self.metadata_json = metadata

    @property
    def tension_weight(self) -> float:
        return float((self.metadata_json or {}).get("tension_weight") or 1.0)

    @tension_weight.setter
    def tension_weight(self, value: float) -> None:
        metadata = dict(self.metadata_json or {})
        metadata["tension_weight"] = float(value)
        self.metadata_json = metadata

    @property
    def conflict_behavior(self) -> str:
        return str((self.metadata_json or {}).get("conflict_behavior") or "additive")

    @conflict_behavior.setter
    def conflict_behavior(self, value: str) -> None:
        metadata = dict(self.metadata_json or {})
        metadata["conflict_behavior"] = value
        self.metadata_json = metadata

    @property
    def cardinality(self) -> str:
        return str((self.metadata_json or {}).get("cardinality") or "multi")

    @cardinality.setter
    def cardinality(self, value: str) -> None:
        metadata = dict(self.metadata_json or {})
        metadata["cardinality"] = value
        self.metadata_json = metadata

    @property
    def space_time_frame_id(self) -> str | None:
        value = (self.metadata_json or {}).get("space_time_frame_id")
        return str(value) if value else None

    @space_time_frame_id.setter
    def space_time_frame_id(self, value: str | None) -> None:
        metadata = dict(self.metadata_json or {})
        metadata["space_time_frame_id"] = value
        self.metadata_json = metadata

    @property
    def updated_at(self) -> datetime | None:
        value = (self.metadata_json or {}).get("updated_at")
        if isinstance(value, datetime):
            return value
        if isinstance(value, str) and value:
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                return None
        return None

    @updated_at.setter
    def updated_at(self, value: datetime | None) -> None:
        metadata = dict(self.metadata_json or {})
        metadata["updated_at"] = value.isoformat() if value is not None else None
        self.metadata_json = metadata

    def debug_repr(self) -> str:
        return (
            f"[CLAIM] {self.claim_type}/{self.claim_group} "
            f"{self.subject_text} --{self.predicate}--> {self.object_text} "
            f"status={self.claim_status} conf={self.confidence} "
            f"sim_w={self.similarity_weight} tension_w={self.tension_weight} "
            f"behavior={self.conflict_behavior}"
        )
