from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, select

from apps.knowledge.domain.claim import Claim
from apps.knowledge.domain.interpretation_run import InterpretationRun
from apps.knowledge.domain.mention import Mention
from apps.knowledge.domain.sentence_interpretation import SentenceInterpretation
from apps.knowledge.domain.space_time_frame import SpaceTimeFrame
from apps.knowledge.models import (
    KnowledgeClaimORM,
    KnowledgeInterpretationRunORM,
    KnowledgeMentionORM,
    KnowledgeSentenceInterpretationORM,
    KnowledgeSpaceTimeFrameORM,
)


def _interpretation_run_to_domain(row: KnowledgeInterpretationRunORM) -> InterpretationRun:
    return InterpretationRun(
        id=row.id,
        tenant="",
        corpus_uuid=row.corpus_uuid,
        source_id=row.source_id,
        document_id=row.document_id,
        status=row.status,  # type: ignore[arg-type]
        interpreter_type=row.interpreter_type,
        language=row.language,
        error_message=row.error_message,
        created_by=row.created_by,
        created_at=row.created_at,
        updated_at=row.updated_at,
        started_at=row.started_at,
        completed_at=row.completed_at,
        metadata=dict(row.metadata_json or {}),
    )


def _sentence_interpretation_to_domain(row: KnowledgeSentenceInterpretationORM) -> SentenceInterpretation:
    metadata = dict(row.metadata_json or {})
    return SentenceInterpretation(
        id=row.id,
        tenant="",
        corpus_uuid=row.corpus_uuid,
        source_id=row.source_id,
        document_id=row.document_id,
        sentence_id=row.sentence_id,
        interpretation_run_id=row.interpretation_run_id,
        sentence_text=row.sentence_text or "",
        claim_summary=row.claim_summary or "",
        assertion_mode=row.assertion_mode,
        claim_type=row.claim_type,
        time_mode=row.time_mode,
        time_label=row.time_label,
        space_mode=row.space_mode,
        space_label=row.space_label,
        confidence=float(row.confidence or 0.0),
        information_value_score=float(metadata.get("information_value_score") or 0.0),
        information_value_status=str(metadata.get("information_value_status") or "unrated"),
        information_value_reason=metadata.get("information_value_reason"),
        created_at=row.created_at,
        updated_at=row.updated_at,
        metadata=metadata,
    )


def _mention_to_domain(row: KnowledgeMentionORM) -> Mention:
    return Mention(
        id=row.id,
        tenant="",
        corpus_uuid=row.corpus_uuid,
        source_id=row.source_id,
        document_id=row.document_id,
        sentence_id=row.sentence_id,
        interpretation_run_id=row.interpretation_run_id,
        mention_type=row.mention_type,
        text_content=row.text_content or "",
        normalized_value=row.normalized_value,
        char_start=row.char_start,
        char_end=row.char_end,
        confidence=float(row.confidence or 0.0),
        created_at=row.created_at,
        metadata=dict(row.metadata_json or {}),
    )


def _claim_to_domain(row: KnowledgeClaimORM) -> Claim:
    metadata = dict(row.metadata_json or {})
    updated_at_raw = metadata.get("updated_at")
    updated_at: datetime | None = None
    if isinstance(updated_at_raw, datetime):
        updated_at = updated_at_raw
    elif isinstance(updated_at_raw, str) and updated_at_raw:
        try:
            updated_at = datetime.fromisoformat(updated_at_raw)
        except ValueError:
            updated_at = None
    return Claim(
        id=row.id,
        tenant="",
        corpus_uuid=row.corpus_uuid,
        source_id=row.source_id,
        document_id=row.document_id,
        sentence_id=row.sentence_id,
        interpretation_run_id=row.interpretation_run_id,
        subject_mention_id=metadata.get("subject_mention_id"),
        object_mention_id=metadata.get("object_mention_id"),
        subject_text=row.subject_text or "",
        predicate_text=row.predicate_text or "",
        object_text=row.object_text,
        claim_type=row.claim_type,
        claim_group=str(metadata.get("claim_group") or "default"),
        claim_status=str(metadata.get("claim_status") or "active"),
        assertion_mode=row.assertion_mode,
        time_mode=row.time_mode,
        time_label=row.time_label,
        space_mode=row.space_mode,
        space_label=row.space_label,
        confidence=float(row.confidence or 0.5),
        identity_weight=float(metadata.get("identity_weight") or 0.0),
        similarity_weight=float(metadata.get("similarity_weight") or 1.0),
        tension_weight=float(metadata.get("tension_weight") or 1.0),
        conflict_behavior=str(metadata.get("conflict_behavior") or "additive"),
        cardinality=str(metadata.get("cardinality") or "multi"),
        space_time_frame_id=metadata.get("space_time_frame_id"),
        created_at=row.created_at,
        updated_at=updated_at,
        metadata=metadata,
    )


def _space_time_frame_to_domain(row: KnowledgeSpaceTimeFrameORM) -> SpaceTimeFrame:
    return SpaceTimeFrame(
        id=row.id,
        claim_id=row.claim_id,
        sentence_id=row.sentence_id,
        source_id=row.source_id,
        language=row.language or "unknown",
        time_mode=row.time_mode,
        time_value=row.time_value,
        time_start=row.time_start,
        time_end=row.time_end,
        time_precision=row.time_precision,
        time_confidence=float(row.time_confidence or 0.5),
        space_mode=row.space_mode,
        space_value=row.space_value,
        space_precision=row.space_precision,
        space_confidence=float(row.space_confidence or 0.5),
        overall_confidence=float(row.overall_confidence or 0.5),
        created_at=row.created_at,
    )


class SQLAlchemyInterpretationRunStore:
    def __init__(self, session_factory) -> None:
        self._sf = session_factory

    def create(self, run: InterpretationRun) -> InterpretationRun:
        with self._sf() as session:
            row = KnowledgeInterpretationRunORM(
                id=run.id,
                corpus_uuid=run.corpus_uuid,
                source_id=run.source_id,
                document_id=run.document_id,
                status=run.status,
                interpreter_type=run.interpreter_type,
                language=run.language,
                error_message=run.error_message,
                metadata_json=dict(run.metadata or {}),
                created_at=run.created_at,
                updated_at=run.updated_at,
                created_by=run.created_by,
                started_at=run.started_at,
                completed_at=run.completed_at,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return _interpretation_run_to_domain(row)

    def update(self, run: InterpretationRun) -> InterpretationRun:
        with self._sf() as session:
            row = session.get(KnowledgeInterpretationRunORM, run.id)
            if row is None:
                raise ValueError(f"Interpretation run not found: {run.id}")
            row.status = run.status
            row.interpreter_type = run.interpreter_type
            row.language = run.language
            row.error_message = run.error_message
            row.metadata_json = dict(run.metadata or {})
            row.updated_at = run.updated_at
            row.started_at = run.started_at
            row.completed_at = run.completed_at
            session.commit()
            session.refresh(row)
            return _interpretation_run_to_domain(row)

    def get_for_document(self, document_id: str) -> InterpretationRun | None:
        with self._sf() as session:
            row = session.execute(
                select(KnowledgeInterpretationRunORM)
                .where(KnowledgeInterpretationRunORM.document_id == document_id)
                .order_by(KnowledgeInterpretationRunORM.created_at.desc())
            ).scalar_one_or_none()
            return _interpretation_run_to_domain(row) if row else None

    def list_for_corpus(self, corpus_uuid: str, *, limit: int = 20) -> list[InterpretationRun]:
        with self._sf() as session:
            rows = session.execute(
                select(KnowledgeInterpretationRunORM)
                .where(KnowledgeInterpretationRunORM.corpus_uuid == corpus_uuid)
                .order_by(KnowledgeInterpretationRunORM.created_at.desc())
                .limit(limit)
            ).scalars()
            return [_interpretation_run_to_domain(row) for row in rows]

    def delete_for_document(self, document_id: str) -> int:
        with self._sf() as session:
            result = session.execute(delete(KnowledgeInterpretationRunORM).where(KnowledgeInterpretationRunORM.document_id == document_id))
            session.commit()
            return int(result.rowcount or 0)

    def delete_for_corpus(self, corpus_uuid: str) -> int:
        with self._sf() as session:
            result = session.execute(delete(KnowledgeInterpretationRunORM).where(KnowledgeInterpretationRunORM.corpus_uuid == corpus_uuid))
            session.commit()
            return int(result.rowcount or 0)


class SQLAlchemySentenceInterpretationStore:
    def __init__(self, session_factory) -> None:
        self._sf = session_factory

    def create_many(self, items: list[SentenceInterpretation]) -> list[SentenceInterpretation]:
        if not items:
            return []
        with self._sf() as session:
            rows = [
                KnowledgeSentenceInterpretationORM(
                    id=item.id,
                    corpus_uuid=item.corpus_uuid,
                    source_id=item.source_id,
                    document_id=item.document_id,
                    sentence_id=item.sentence_id,
                    interpretation_run_id=item.interpretation_run_id,
                    sentence_text=item.sentence_text,
                    claim_summary=item.claim_summary,
                    assertion_mode=item.assertion_mode,
                    claim_type=item.claim_type,
                    time_mode=item.time_mode,
                    time_label=item.time_label,
                    space_mode=item.space_mode,
                    space_label=item.space_label,
                    confidence=item.confidence,
                    metadata_json={
                        **dict(item.metadata or {}),
                        "information_value_score": item.information_value_score,
                        "information_value_status": item.information_value_status,
                        "information_value_reason": item.information_value_reason,
                    },
                    created_at=item.created_at,
                    updated_at=item.updated_at,
                )
                for item in items
            ]
            session.add_all(rows)
            session.commit()
            for row in rows:
                session.refresh(row)
            return [_sentence_interpretation_to_domain(row) for row in rows]

    def get_for_sentence(self, sentence_id: str) -> SentenceInterpretation | None:
        with self._sf() as session:
            row = session.execute(
                select(KnowledgeSentenceInterpretationORM).where(KnowledgeSentenceInterpretationORM.sentence_id == sentence_id)
            ).scalar_one_or_none()
            return _sentence_interpretation_to_domain(row) if row else None

    def delete_for_document(self, document_id: str) -> int:
        with self._sf() as session:
            result = session.execute(delete(KnowledgeSentenceInterpretationORM).where(KnowledgeSentenceInterpretationORM.document_id == document_id))
            session.commit()
            return int(result.rowcount or 0)

    def delete_for_corpus(self, corpus_uuid: str) -> int:
        with self._sf() as session:
            result = session.execute(delete(KnowledgeSentenceInterpretationORM).where(KnowledgeSentenceInterpretationORM.corpus_uuid == corpus_uuid))
            session.commit()
            return int(result.rowcount or 0)


class SQLAlchemyMentionStore:
    def __init__(self, session_factory) -> None:
        self._sf = session_factory

    def create_many(self, items: list[Mention]) -> list[Mention]:
        if not items:
            return []
        with self._sf() as session:
            rows = [
                KnowledgeMentionORM(
                    id=item.id,
                    corpus_uuid=item.corpus_uuid,
                    source_id=item.source_id,
                    document_id=item.document_id,
                    sentence_id=item.sentence_id,
                    interpretation_run_id=item.interpretation_run_id,
                    mention_type=item.mention_type,
                    text_content=item.text_content,
                    normalized_value=item.normalized_value,
                    char_start=item.char_start,
                    char_end=item.char_end,
                    confidence=item.confidence,
                    metadata_json=dict(item.metadata or {}),
                    created_at=item.created_at,
                )
                for item in items
            ]
            session.add_all(rows)
            session.commit()
            for row in rows:
                session.refresh(row)
            return [_mention_to_domain(row) for row in rows]

    def list_for_sentence(self, sentence_id: str) -> list[Mention]:
        with self._sf() as session:
            rows = session.execute(
                select(KnowledgeMentionORM)
                .where(KnowledgeMentionORM.sentence_id == sentence_id)
                .order_by(KnowledgeMentionORM.char_start.asc(), KnowledgeMentionORM.created_at.asc())
            ).scalars().all()
            return [_mention_to_domain(row) for row in rows]

    def delete_for_document(self, document_id: str) -> int:
        with self._sf() as session:
            result = session.execute(delete(KnowledgeMentionORM).where(KnowledgeMentionORM.document_id == document_id))
            session.commit()
            return int(result.rowcount or 0)

    def delete_for_corpus(self, corpus_uuid: str) -> int:
        with self._sf() as session:
            result = session.execute(delete(KnowledgeMentionORM).where(KnowledgeMentionORM.corpus_uuid == corpus_uuid))
            session.commit()
            return int(result.rowcount or 0)


class SQLAlchemyClaimStore:
    def __init__(self, session_factory) -> None:
        self._sf = session_factory

    def create_many(self, items: list[Claim]) -> list[Claim]:
        if not items:
            return []
        with self._sf() as session:
            rows = [
                KnowledgeClaimORM(
                    id=item.id,
                    corpus_uuid=item.corpus_uuid,
                    source_id=item.source_id,
                    document_id=item.document_id,
                    sentence_id=item.sentence_id,
                    interpretation_run_id=item.interpretation_run_id,
                    subject_text=item.subject_text,
                    predicate_text=item.predicate_text,
                    object_text=item.object_text,
                    claim_type=item.claim_type,
                    assertion_mode=item.assertion_mode,
                    time_mode=item.time_mode,
                    time_label=item.time_label,
                    space_mode=item.space_mode,
                    space_label=item.space_label,
                    confidence=item.confidence,
                    metadata_json={
                        **dict(item.metadata or {}),
                        "subject_mention_id": item.subject_mention_id,
                        "object_mention_id": item.object_mention_id,
                        "claim_group": item.claim_group,
                        "claim_status": item.claim_status,
                        "claim_text": item.claim_text,
                        "identity_weight": item.identity_weight,
                        "similarity_weight": item.similarity_weight,
                        "tension_weight": item.tension_weight,
                        "conflict_behavior": item.conflict_behavior,
                        "cardinality": item.cardinality,
                        "space_time_frame_id": item.space_time_frame_id,
                        "updated_at": item.updated_at.isoformat() if item.updated_at is not None else None,
                    },
                    created_at=item.created_at,
                )
                for item in items
            ]
            session.add_all(rows)
            session.commit()
            for row in rows:
                session.refresh(row)
            return [_claim_to_domain(row) for row in rows]

    def list_for_sentence(self, sentence_id: str) -> list[Claim]:
        with self._sf() as session:
            rows = session.execute(
                select(KnowledgeClaimORM)
                .where(KnowledgeClaimORM.sentence_id == sentence_id)
                .order_by(KnowledgeClaimORM.created_at.asc())
            ).scalars().all()
            return [_claim_to_domain(row) for row in rows]

    def delete_for_document(self, document_id: str) -> int:
        with self._sf() as session:
            result = session.execute(delete(KnowledgeClaimORM).where(KnowledgeClaimORM.document_id == document_id))
            session.commit()
            return int(result.rowcount or 0)

    def delete_for_corpus(self, corpus_uuid: str) -> int:
        with self._sf() as session:
            result = session.execute(delete(KnowledgeClaimORM).where(KnowledgeClaimORM.corpus_uuid == corpus_uuid))
            session.commit()
            return int(result.rowcount or 0)


class SQLAlchemySpaceTimeFrameStore:
    def __init__(self, session_factory) -> None:
        self._sf = session_factory

    def create_many(self, items: list[SpaceTimeFrame]) -> list[SpaceTimeFrame]:
        if not items:
            return []
        with self._sf() as session:
            rows = [
                KnowledgeSpaceTimeFrameORM(
                    id=item.id,
                    claim_id=item.claim_id,
                    sentence_id=item.sentence_id,
                    source_id=item.source_id,
                    language=item.language,
                    time_mode=item.time_mode,
                    time_value=item.time_value,
                    time_start=item.time_start,
                    time_end=item.time_end,
                    time_precision=item.time_precision,
                    time_confidence=item.time_confidence,
                    space_mode=item.space_mode,
                    space_value=item.space_value,
                    space_precision=item.space_precision,
                    space_confidence=item.space_confidence,
                    overall_confidence=item.overall_confidence,
                    created_at=item.created_at,
                )
                for item in items
            ]
            session.add_all(rows)
            session.commit()
            for row in rows:
                session.refresh(row)
            return [_space_time_frame_to_domain(row) for row in rows]

    def list_for_sentence(self, sentence_id: str) -> list[SpaceTimeFrame]:
        with self._sf() as session:
            rows = session.execute(
                select(KnowledgeSpaceTimeFrameORM)
                .where(KnowledgeSpaceTimeFrameORM.sentence_id == sentence_id)
                .order_by(KnowledgeSpaceTimeFrameORM.created_at.asc())
            ).scalars().all()
            return [_space_time_frame_to_domain(row) for row in rows]

    def list_for_claim_ids(self, claim_ids: list[str]) -> list[SpaceTimeFrame]:
        if not claim_ids:
            return []
        with self._sf() as session:
            rows = session.execute(
                select(KnowledgeSpaceTimeFrameORM)
                .where(KnowledgeSpaceTimeFrameORM.claim_id.in_(claim_ids))
                .order_by(KnowledgeSpaceTimeFrameORM.created_at.asc())
            ).scalars().all()
            return [_space_time_frame_to_domain(row) for row in rows]

    def delete_for_document(self, document_id: str) -> int:
        with self._sf() as session:
            result = session.execute(
                delete(KnowledgeSpaceTimeFrameORM).where(
                    KnowledgeSpaceTimeFrameORM.claim_id.in_(
                        select(KnowledgeClaimORM.id).where(KnowledgeClaimORM.document_id == document_id)
                    )
                )
            )
            session.commit()
            return int(result.rowcount or 0)

    def delete_for_corpus(self, corpus_uuid: str) -> int:
        with self._sf() as session:
            result = session.execute(
                delete(KnowledgeSpaceTimeFrameORM).where(
                    KnowledgeSpaceTimeFrameORM.claim_id.in_(
                        select(KnowledgeClaimORM.id).where(KnowledgeClaimORM.corpus_uuid == corpus_uuid)
                    )
                )
            )
            session.commit()
            return int(result.rowcount or 0)


__all__ = [
    "SQLAlchemyClaimStore",
    "SQLAlchemyInterpretationRunStore",
    "SQLAlchemyMentionStore",
    "SQLAlchemySentenceInterpretationStore",
    "SQLAlchemySpaceTimeFrameStore",
]
