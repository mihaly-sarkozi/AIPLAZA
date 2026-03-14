from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint, Text
from datetime import datetime

from apps.auth.infrastructure.db.models.base import TenantSchemaBase


PERSONAL_DATA_MODE_NO = "no_personal_data"
PERSONAL_DATA_MODE_CONFIRM = "with_confirmation"
PERSONAL_DATA_MODE_ALLOWED = "allowed_not_to_ai"

PERSONAL_DATA_SENSITIVITY_WEAK = "weak"
PERSONAL_DATA_SENSITIVITY_MEDIUM = "medium"
PERSONAL_DATA_SENSITIVITY_STRONG = "strong"


class KBORM(TenantSchemaBase):
    __tablename__ = "knowledge_bases"

    id = Column(Integer, primary_key=True)
    uuid = Column(String(36), unique=True, nullable=False, index=True)
    name = Column(String(20), unique=True, nullable=False)
    description = Column(String(1024))
    qdrant_collection_name = Column(String(128), unique=True, nullable=False)
    personal_data_mode = Column(String(32), nullable=False, default=PERSONAL_DATA_MODE_NO)
    personal_data_sensitivity = Column(String(16), nullable=False, default=PERSONAL_DATA_SENSITIVITY_MEDIUM)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class KbTrainingLogORM(TenantSchemaBase):
    """Tanítási napló: ki, mikor, milyen címmel/tartalommal tanított (Qdrant point_id egyezik)."""
    __tablename__ = "kb_training_log"

    id = Column(Integer, primary_key=True)
    kb_id = Column(Integer, ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False, index=True)
    point_id = Column(String(36), nullable=False, index=True)  # Qdrant point UUID
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    user_display = Column(String(255), nullable=True)  # név vagy email a megjelenítéshez
    title = Column(String(512), nullable=False)
    content = Column(Text, nullable=True)  # sanitized content (PII replaced with refs)
    raw_content = Column(Text, nullable=True)  # original content before PII replacement
    review_decision = Column(String(64), nullable=True)  # mask_all | keep_role_based_emails | reject | continue_sanitized
    created_at = Column(DateTime, default=datetime.utcnow)


class KbPersonalDataORM(TenantSchemaBase):
    """Kiszűrt személyes adatok tárolása; a tanítási tartalomban [típus_reference_id] szerepel."""
    __tablename__ = "kb_personal_data"

    id = Column(Integer, primary_key=True)
    kb_id = Column(Integer, ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False, index=True)
    data_type = Column(String(64), nullable=False, index=True)  # pl. név, születési_dátum, email
    extracted_value = Column(Text, nullable=False)  # az eredeti érték
    reference_id = Column(String(36), nullable=False, index=True)  # a [típus_reference_id] azonosító


class KbUserPermissionORM(TenantSchemaBase):
    """Tudástár–felhasználó jogosultság: use = használhatja (chat), train = taníthatja."""
    __tablename__ = "kb_user_permission"
    __table_args__ = (UniqueConstraint("kb_id", "user_id", name="uq_kb_user_permission_kb_user"),)

    id = Column(Integer, primary_key=True)
    kb_id = Column(Integer, ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    permission = Column(String(10), nullable=False)  # 'use' | 'train'
