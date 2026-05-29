# Ez a fájl az adott terület adatmodelljeit és kapcsolódó struktúráit tartalmazza.
from sqlalchemy import BigInteger, Boolean, Column, Integer, String, DateTime

from .base import TenantSchemaBase
from .utils import _utcnow_naive
from .constants import (
    PERSONAL_DATA_MODE_NO,
    PERSONAL_DATA_SENSITIVITY_MEDIUM,
)


class KBORM(TenantSchemaBase):
    __tablename__ = "knowledge_bases"

    id = Column(Integer, primary_key=True)
    uuid = Column(String(36), unique=True, nullable=False, index=True)
    name = Column(String(200), unique=True, nullable=False)
    description = Column(String(1024))
    qdrant_collection_name = Column(String(128), unique=True, nullable=False)
    personal_data_mode = Column(String(32), nullable=False, default=PERSONAL_DATA_MODE_NO)
    personal_data_sensitivity = Column(String(16), nullable=False, default=PERSONAL_DATA_SENSITIVITY_MEDIUM)
    pii_depersonalization_enabled = Column(Boolean, nullable=False, default=True)
    public_enabled = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=_utcnow_naive)
    created_by = Column(Integer, nullable=False)
    updated_at = Column(DateTime, default=_utcnow_naive, onupdate=_utcnow_naive)
    updated_by = Column(Integer, nullable=False)
    deleted_at = Column(DateTime, nullable=True, index=True)
    deleted_display_name = Column(String(200), nullable=True)
    deleted_training_char_count = Column(BigInteger, nullable=False, default=0)
