from sqlalchemy import Column, DateTime, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB

from .base import TenantSchemaBase
from .utils import _utcnow_naive


class KnowledgeMentionORM(TenantSchemaBase):
    __tablename__ = "knowledge_mentions"

    id = Column(String(36), primary_key=True)
    corpus_uuid = Column(String(36), nullable=False, index=True)
    source_id = Column(String(36), nullable=False, index=True)
    document_id = Column(String(36), nullable=False, index=True)
    # TODO: promote this to an actual ForeignKey via migration when the schema is updated.
    sentence_id = Column(String(36), nullable=False, index=True)
    interpretation_run_id = Column(String(36), nullable=False, index=True)
    # Kept as String for compatibility; no enum migration is required yet.
    mention_type = Column(String(32), nullable=False, default="unknown", index=True)
    text_content = Column(Text, nullable=False, default="")
    normalized_value = Column(Text, nullable=True)
    char_start = Column(Integer, nullable=False, default=0)
    char_end = Column(Integer, nullable=False, default=0)
    confidence = Column(Float, nullable=False, default=0.5)
    metadata_json = Column("metadata", JSONB, nullable=False, default=dict)
    created_at = Column(DateTime, default=_utcnow_naive, nullable=False)

    @property
    def mention_id(self) -> str:
        return self.id

    @mention_id.setter
    def mention_id(self, value: str) -> None:
        self.id = value

    @property
    def surface_text(self) -> str:
        return self.text_content

    @surface_text.setter
    def surface_text(self, value: str) -> None:
        self.text_content = value

    @property
    def normalized_text(self) -> str:
        return self.normalized_value or ""

    @normalized_text.setter
    def normalized_text(self, value: str) -> None:
        self.normalized_value = value

    def debug_repr(self) -> str:
        return f"[MENTION] {self.surface_text} ({self.mention_type}) @ {self.char_start}-{self.char_end} | norm={self.normalized_text}"
