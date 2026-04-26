from sqlalchemy import Column, DateTime, Float, String

from .base import TenantSchemaBase
from .utils import _utcnow_naive


class KnowledgeSpaceTimeFrameORM(TenantSchemaBase):
    __tablename__ = "knowledge_space_time_frames"

    id = Column(String(36), primary_key=True)
    # TODO: add dedicated FK constraints for claim_id/sentence_id/source_id and create the table via migration.
    claim_id = Column(String(36), nullable=True, index=True)
    sentence_id = Column(String(36), nullable=True, index=True)
    source_id = Column(String(36), nullable=True, index=True)
    language = Column(String(16), nullable=False, default="unknown", index=True)
    time_mode = Column(String(32), nullable=False, default="unknown", index=True)
    time_value = Column(String(255), nullable=True)
    time_start = Column(DateTime, nullable=True)
    time_end = Column(DateTime, nullable=True)
    time_precision = Column(String(64), nullable=True)
    time_confidence = Column(Float, nullable=False, default=0.5)
    space_mode = Column(String(32), nullable=False, default="unknown", index=True)
    space_value = Column(String(255), nullable=True)
    space_precision = Column(String(64), nullable=True)
    space_confidence = Column(Float, nullable=False, default=0.5)
    overall_confidence = Column(Float, nullable=False, default=0.5)
    created_at = Column(DateTime, default=_utcnow_naive, nullable=False)

    @property
    def frame_id(self) -> str:
        return self.id

    @frame_id.setter
    def frame_id(self, value: str) -> None:
        self.id = value

    def debug_repr(self) -> str:
        return (
            f"[SPACE-TIME] time={self.time_mode}:{self.time_value} "
            f"space={self.space_mode}:{self.space_value} conf={self.overall_confidence}"
        )
