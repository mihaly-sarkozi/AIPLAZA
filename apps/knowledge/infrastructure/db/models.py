from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    Text,
    Float,
    JSON,
    Index,
)
from datetime import UTC, datetime

from apps.auth.infrastructure.db.models.base import TenantSchemaBase


def _utcnow_naive() -> datetime:
    """UTC now timezone-naive formában (SQLAlchemy defaulthoz)."""
    return datetime.now(UTC).replace(tzinfo=None)


PERSONAL_DATA_MODE_NO = "no_personal_data"
PERSONAL_DATA_MODE_CONFIRM = "with_confirmation"
PERSONAL_DATA_MODE_ALLOWED = "allowed_not_to_ai"
PERSONAL_DATA_MODE_DISABLED = "no_pii_filter"

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
    created_at = Column(DateTime, default=_utcnow_naive)
    updated_at = Column(DateTime, default=_utcnow_naive)


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
    review_decision = Column(Text, nullable=True)  # mask_all | continue_sanitized | JSON pii_decisions
    idempotency_key = Column(String(128), nullable=True, index=True)
    created_at = Column(DateTime, default=_utcnow_naive)


class KbPersonalDataORM(TenantSchemaBase):
    """Kiszűrt személyes adatok tárolása; a tanítási tartalomban [típus_reference_id] szerepel."""
    __tablename__ = "kb_personal_data"

    id = Column(Integer, primary_key=True)
    kb_id = Column(Integer, ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False, index=True)
    point_id = Column(String(36), nullable=False, index=True)  # kb_training_log.point_id – melyik bejegyzéshez tartozik
    data_type = Column(String(64), nullable=False, index=True)  # pl. név, születési_dátum, email
    extracted_value = Column(Text, nullable=False)  # az eredeti érték
    reference_id = Column(String(36), nullable=False, index=True)  # a [típus_reference_id] azonosító
    created_at = Column(DateTime, default=_utcnow_naive, nullable=False)
    expires_at = Column(DateTime, nullable=True, index=True)


class KbUserPermissionORM(TenantSchemaBase):
    """Tudástár–felhasználó jogosultság: use = használhatja (chat), train = taníthatja."""
    __tablename__ = "kb_user_permission"
    __table_args__ = (UniqueConstraint("kb_id", "user_id", name="uq_kb_user_permission_kb_user"),)

    id = Column(Integer, primary_key=True)
    kb_id = Column(Integer, ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    permission = Column(String(10), nullable=False)  # 'use' | 'train'


class KbSentenceORM(TenantSchemaBase):
    """Sanitized mondatok egy train pointból."""
    __tablename__ = "kb_sentences"
    __table_args__ = (
        Index("ix_kb_sentences_kb_source", "kb_id", "source_point_id"),
    )

    id = Column(Integer, primary_key=True)
    kb_id = Column(Integer, ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False, index=True)
    source_point_id = Column(String(36), nullable=False, index=True)
    sentence_order = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)
    sanitized_text = Column(Text, nullable=False)
    token_count = Column(Integer, nullable=False, default=0)
    entity_ids = Column(JSON, nullable=False, default=list)
    assertion_ids = Column(JSON, nullable=False, default=list)
    predicate_hints = Column(JSON, nullable=False, default=list)
    place_ids = Column(JSON, nullable=False, default=list)
    # Legacy oszlopnevek, de kizárólag valid_time_from / valid_time_to jelentéssel.
    # A mondat valid_time vetületét hordozzák a kapcsolt assertionökből.
    time_from = Column(DateTime, nullable=True, index=True)
    time_to = Column(DateTime, nullable=True, index=True)
    place_keys = Column(JSON, nullable=False, default=list)
    qdrant_point_id = Column(String(64), nullable=True, index=True)
    created_at = Column(DateTime, default=_utcnow_naive, nullable=False)


class KbMentionORM(TenantSchemaBase):
    """Mondatbeli entity említések és feloldásuk."""
    __tablename__ = "kb_mentions"

    id = Column(Integer, primary_key=True)
    sentence_id = Column(Integer, ForeignKey("kb_sentences.id", ondelete="CASCADE"), nullable=False, index=True)
    surface_form = Column(String(512), nullable=False)
    mention_type = Column(String(64), nullable=False, index=True)
    grammatical_role = Column(String(64), nullable=True)
    sentence_local_index = Column(Integer, nullable=True)
    char_start = Column(Integer, nullable=True)
    char_end = Column(Integer, nullable=True)
    resolved_entity_id = Column(Integer, ForeignKey("kb_entities.id", ondelete="SET NULL"), nullable=True, index=True)
    resolution_confidence = Column(Float, nullable=True)
    is_implicit_subject = Column(Integer, nullable=False, default=0)  # 0/1
    created_at = Column(DateTime, default=_utcnow_naive, nullable=False)


class KbEntityORM(TenantSchemaBase):
    """Canonicalizált entitások KB-n belül."""
    __tablename__ = "kb_entities"
    __table_args__ = (
        Index("ix_kb_entities_kb_canonical_name", "kb_id", "canonical_name"),
    )

    id = Column(Integer, primary_key=True)
    kb_id = Column(Integer, ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False, index=True)
    source_point_id = Column(String(36), nullable=True, index=True)
    canonical_name = Column(String(512), nullable=False)
    canonical_key = Column(String(512), nullable=True, index=True)
    entity_type = Column(String(64), nullable=False, index=True)
    aliases = Column(JSON, nullable=False, default=list)
    confidence = Column(Float, nullable=True)
    first_seen_at = Column(DateTime, default=_utcnow_naive, nullable=False)
    last_seen_at = Column(DateTime, default=_utcnow_naive, nullable=False)


class KbEntityAliasORM(TenantSchemaBase):
    """Entitás aliasok külön táblában (gyors kereséshez)."""
    __tablename__ = "kb_entity_aliases"
    __table_args__ = (
        UniqueConstraint("entity_id", "alias", name="uq_kb_entity_alias_entity_alias"),
        Index("ix_kb_entity_aliases_entity_alias_text", "entity_id", "alias_text"),
        Index("ix_kb_entity_aliases_alias", "alias"),
    )

    id = Column(Integer, primary_key=True)
    entity_id = Column(Integer, ForeignKey("kb_entities.id", ondelete="CASCADE"), nullable=False, index=True)
    alias = Column(String(512), nullable=False)
    alias_text = Column(String(512), nullable=True, index=True)


class KbTimeIntervalORM(TenantSchemaBase):
    """Normalizált időintervallumok."""
    __tablename__ = "kb_time_intervals"

    id = Column(Integer, primary_key=True)
    kb_id = Column(Integer, ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False, index=True)
    source_point_id = Column(String(36), nullable=False, index=True)
    normalized_text = Column(String(256), nullable=False)
    valid_from = Column(DateTime, nullable=True, index=True)
    valid_to = Column(DateTime, nullable=True, index=True)
    granularity = Column(String(32), nullable=False, default="unknown")
    confidence = Column(Float, nullable=True)
    created_at = Column(DateTime, default=_utcnow_naive, nullable=False)


class KbPlaceORM(TenantSchemaBase):
    """Normalizált helyek KB-n belül."""
    __tablename__ = "kb_places"
    __table_args__ = (
        Index("ix_kb_places_kb_name", "kb_id", "canonical_name"),
        Index("ix_kb_places_kb_key", "kb_id", "normalized_key"),
        Index("ix_kb_places_kb_parent", "kb_id", "parent_place_id"),
    )

    id = Column(Integer, primary_key=True)
    kb_id = Column(Integer, ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False, index=True)
    canonical_name = Column(String(256), nullable=False)
    normalized_key = Column(String(256), nullable=False, index=True)
    place_type = Column(String(64), nullable=True, index=True)
    country_code = Column(String(8), nullable=True, index=True)
    parent_place_id = Column(Integer, ForeignKey("kb_places.id", ondelete="SET NULL"), nullable=True, index=True)
    confidence = Column(Float, nullable=False, default=0.0)
    created_at = Column(DateTime, default=_utcnow_naive, nullable=False)


class KbAssertionORM(TenantSchemaBase):
    """Assertion tudásmagok."""
    __tablename__ = "kb_assertions"
    __table_args__ = (
        Index("ix_kb_assertions_kb_fingerprint", "kb_id", "assertion_fingerprint"),
        Index("ix_kb_assertions_kb_subject", "kb_id", "subject_entity_id"),
        Index("ix_kb_assertions_kb_predicate", "kb_id", "predicate"),
        Index("ix_kb_assertions_kb_time_interval", "kb_id", "time_interval_id"),
        Index("ix_kb_assertions_kb_source", "kb_id", "source_point_id"),
        Index("ix_kb_assertions_kb_time", "kb_id", "time_from", "time_to"),
        Index("ix_kb_assertions_kb_place", "kb_id", "place_key"),
    )

    id = Column(Integer, primary_key=True)
    kb_id = Column(Integer, ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False, index=True)
    source_point_id = Column(String(36), nullable=False, index=True)
    source_document_title = Column(String(512), nullable=True)
    source_sentence_id = Column(Integer, ForeignKey("kb_sentences.id", ondelete="SET NULL"), nullable=True, index=True)
    assertion_primary_subject_mention_id = Column(Integer, ForeignKey("kb_mentions.id", ondelete="SET NULL"), nullable=True, index=True)
    subject_resolution_type = Column(String(16), nullable=False, default="explicit")
    subject_entity_id = Column(Integer, ForeignKey("kb_entities.id", ondelete="SET NULL"), nullable=True, index=True)
    predicate = Column(String(128), nullable=False)
    object_entity_id = Column(Integer, ForeignKey("kb_entities.id", ondelete="SET NULL"), nullable=True, index=True)
    object_value = Column(Text, nullable=True)
    time_interval_id = Column(Integer, ForeignKey("kb_time_intervals.id", ondelete="SET NULL"), nullable=True, index=True)
    place_id = Column(Integer, ForeignKey("kb_places.id", ondelete="SET NULL"), nullable=True, index=True)
    # Legacy oszlopnevek, de kizárólag valid_time_from / valid_time_to jelentéssel.
    # valid_time: mikor igaz az assertion a világban
    time_from = Column(DateTime, nullable=True, index=True)
    time_to = Column(DateTime, nullable=True, index=True)
    place_key = Column(String(256), nullable=True, index=True)
    attributes = Column(JSON, nullable=False, default=list)
    modality = Column(String(32), nullable=False, default="asserted")
    polarity = Column(String(32), nullable=False, default="positive")
    canonical_text = Column(Text, nullable=False)
    confidence = Column(Float, nullable=False, default=0.0)
    strength = Column(Float, nullable=False, default=0.05)
    baseline_strength = Column(Float, nullable=False, default=0.05)
    decay_rate = Column(Float, nullable=False, default=0.015)
    reinforcement_count = Column(Integer, nullable=False, default=0)
    evidence_count = Column(Integer, nullable=False, default=0)
    source_diversity = Column(Integer, nullable=False, default=1)
    first_seen_at = Column(DateTime, default=_utcnow_naive, nullable=False)
    last_reinforced_at = Column(DateTime, default=_utcnow_naive, nullable=False)
    # source_time: a dokumentum/forrás időbélyege (nem valid_time)
    source_time = Column(DateTime, nullable=True, index=True)
    # ingest_time: mikor került be a tudástárba (nem valid_time)
    ingest_time = Column(DateTime, default=_utcnow_naive, nullable=False, index=True)
    status = Column(String(32), nullable=False, default="active")
    assertion_fingerprint = Column(String(128), nullable=False, index=True)
    qdrant_point_id = Column(String(64), nullable=True, index=True)


class KbStructuralChunkORM(TenantSchemaBase):
    """Szerkezeti chunkok retrievalhez."""
    __tablename__ = "kb_structural_chunks"
    __table_args__ = (
        Index("ix_kb_structural_chunks_kb_source", "kb_id", "source_point_id"),
    )

    id = Column(Integer, primary_key=True)
    kb_id = Column(Integer, ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False, index=True)
    source_point_id = Column(String(36), nullable=False, index=True)
    chunk_order = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)
    sentence_ids = Column(JSON, nullable=False, default=list)
    assertion_ids = Column(JSON, nullable=False, default=list)
    entity_ids = Column(JSON, nullable=False, default=list)
    predicate_hints = Column(JSON, nullable=False, default=list)
    place_ids = Column(JSON, nullable=False, default=list)
    token_count = Column(Integer, nullable=False, default=0)
    # Legacy oszlopnevek, de kizárólag valid_time_from / valid_time_to jelentéssel.
    # A chunk valid_time vetületét hordozzák a lefedett assertion/sentence halmazból.
    time_from = Column(DateTime, nullable=True, index=True)
    time_to = Column(DateTime, nullable=True, index=True)
    place_keys = Column(JSON, nullable=False, default=list)
    qdrant_point_id = Column(String(64), nullable=True, index=True)
    created_at = Column(DateTime, default=_utcnow_naive, nullable=False)


class KbAssertionEvidenceORM(TenantSchemaBase):
    """Assertion ↔ mondat evidencia kapcsolat."""
    __tablename__ = "kb_assertion_evidence"
    __table_args__ = (
        UniqueConstraint("assertion_id", "sentence_id", name="uq_kb_assertion_evidence_pair"),
    )

    id = Column(Integer, primary_key=True)
    kb_id = Column(Integer, ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False, index=True)
    assertion_id = Column(Integer, ForeignKey("kb_assertions.id", ondelete="CASCADE"), nullable=False, index=True)
    sentence_id = Column(Integer, ForeignKey("kb_sentences.id", ondelete="CASCADE"), nullable=False, index=True)
    source_point_id = Column(String(36), nullable=False, index=True)
    evidence_type = Column(String(16), nullable=False, default="PRIMARY")
    confidence = Column(Float, nullable=True)
    weight = Column(Float, nullable=False, default=1.0)
    created_at = Column(DateTime, default=_utcnow_naive, nullable=False)


class KbAssertionRelationORM(TenantSchemaBase):
    """Lokális assertion gráf kapcsolatok (MVP)."""
    __tablename__ = "kb_assertion_relations"
    __table_args__ = (
        Index("ix_kb_assertion_rel_kb_from", "kb_id", "from_assertion_id"),
        Index("ix_kb_assertion_rel_kb_to", "kb_id", "to_assertion_id"),
        Index("ix_kb_assertion_rel_kb_type_conf", "kb_id", "relation_type", "relation_confidence"),
    )

    id = Column(Integer, primary_key=True)
    kb_id = Column(Integer, ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False, index=True)
    from_assertion_id = Column(Integer, ForeignKey("kb_assertions.id", ondelete="CASCADE"), nullable=False, index=True)
    to_assertion_id = Column(Integer, ForeignKey("kb_assertions.id", ondelete="CASCADE"), nullable=False, index=True)
    relation_type = Column(String(64), nullable=False, index=True)
    weight = Column(Float, nullable=False, default=1.0)
    relation_confidence = Column(Float, nullable=False, default=0.0)
    created_at = Column(DateTime, default=_utcnow_naive, nullable=False)


class KbReinforcementEventORM(TenantSchemaBase):
    """Erősítési események (training/retrieval/followup)."""
    __tablename__ = "kb_reinforcement_events"
    __table_args__ = (
        Index("ix_kb_reinforce_kb_target", "kb_id", "target_type", "target_id"),
    )

    id = Column(Integer, primary_key=True)
    kb_id = Column(Integer, ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False, index=True)
    target_type = Column(String(32), nullable=False, index=True)  # assertion | entity | chunk | sentence
    target_id = Column(Integer, nullable=False, index=True)
    event_type = Column(String(32), nullable=False, index=True)  # explicit_training | retrieval_hit | followup
    weight = Column(Float, nullable=False, default=1.0)
    created_at = Column(DateTime, default=_utcnow_naive, nullable=False)


class KbVectorOutboxORM(TenantSchemaBase):
    """Qdrant műveleti outbox (retry workerhez)."""
    __tablename__ = "kb_vector_outbox"
    __table_args__ = (
        Index("ix_kb_vector_outbox_status_next_retry", "status", "next_retry_at"),
        Index("ix_kb_vector_outbox_kb_status", "kb_id", "status"),
    )

    id = Column(Integer, primary_key=True)
    kb_id = Column(Integer, ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False, index=True)
    source_point_id = Column(String(36), nullable=True, index=True)
    operation_type = Column(String(48), nullable=False, index=True)  # reindex_training_point | delete_source_point
    payload = Column(JSON, nullable=False, default=dict)
    status = Column(String(16), nullable=False, default="pending", index=True)  # pending | processing | done | failed
    attempts = Column(Integer, nullable=False, default=0)
    last_error = Column(Text, nullable=True)
    next_retry_at = Column(DateTime, nullable=False, default=_utcnow_naive, index=True)
    created_at = Column(DateTime, default=_utcnow_naive, nullable=False)
    updated_at = Column(DateTime, default=_utcnow_naive, nullable=False)
    processed_at = Column(DateTime, nullable=True)
