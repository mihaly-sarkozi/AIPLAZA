from __future__ import annotations

from sqlalchemy import delete, select

from apps.knowledge.domain.document import Document
from apps.knowledge.domain.paragraph import Paragraph
from apps.knowledge.domain.parser_run import ParserRun
from apps.knowledge.domain.sentence import Sentence
from apps.knowledge.models import (
    KnowledgeDocumentORM,
    KnowledgeParagraphORM,
    KnowledgeParserRunORM,
    KnowledgeSentenceORM,
)


def _parser_run_to_domain(row: KnowledgeParserRunORM) -> ParserRun:
    return ParserRun(
        id=row.id,
        tenant="",
        corpus_uuid=row.corpus_uuid,
        source_id=row.source_id,
        status=row.status,  # type: ignore[arg-type]
        parser_type=row.parser_type,
        language=row.language,
        error_message=row.error_message,
        created_by=row.created_by,
        created_at=row.created_at,
        updated_at=row.updated_at,
        started_at=row.started_at,
        completed_at=row.completed_at,
        metadata=dict(row.metadata_json or {}),
    )


def _document_to_domain(row: KnowledgeDocumentORM) -> Document:
    return Document(
        id=row.id,
        tenant="",
        corpus_uuid=row.corpus_uuid,
        source_id=row.source_id,
        parser_run_id=row.parser_run_id,
        title=row.title,
        language=row.language,
        text_content=row.text_content or "",
        char_count=row.char_count,
        status=row.status,  # type: ignore[arg-type]
        created_at=row.created_at,
        updated_at=row.updated_at,
        metadata=dict(row.metadata_json or {}),
    )


def _paragraph_to_domain(row: KnowledgeParagraphORM) -> Paragraph:
    return Paragraph(
        id=row.id,
        tenant="",
        corpus_uuid=row.corpus_uuid,
        source_id=row.source_id,
        document_id=row.document_id,
        block_id=row.block_id,
        order_index=row.order_index,
        text_content=row.text_content or "",
        char_start=row.char_start,
        char_end=row.char_end,
        sentence_count=row.sentence_count,
        created_at=row.created_at,
        metadata=dict(row.metadata_json or {}),
    )


def _sentence_to_domain(row: KnowledgeSentenceORM) -> Sentence:
    return Sentence(
        id=row.id,
        tenant="",
        corpus_uuid=row.corpus_uuid,
        source_id=row.source_id,
        document_id=row.document_id,
        paragraph_id=row.paragraph_id,
        order_index=row.order_index,
        text_content=row.text_content or "",
        char_start=row.char_start,
        char_end=row.char_end,
        token_count=row.token_count,
        created_at=row.created_at,
        metadata=dict(row.metadata_json or {}),
    )


class SQLAlchemyParserRunStore:
    def __init__(self, session_factory) -> None:
        self._sf = session_factory

    def create(self, run: ParserRun) -> ParserRun:
        with self._sf() as session:
            row = KnowledgeParserRunORM(
                id=run.id,
                corpus_uuid=run.corpus_uuid,
                source_id=run.source_id,
                status=run.status,
                parser_type=run.parser_type,
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
            return _parser_run_to_domain(row)

    def update(self, run: ParserRun) -> ParserRun:
        with self._sf() as session:
            row = session.get(KnowledgeParserRunORM, run.id)
            if row is None:
                raise ValueError(f"Parser run not found: {run.id}")
            row.status = run.status
            row.parser_type = run.parser_type
            row.language = run.language
            row.error_message = run.error_message
            row.metadata_json = dict(run.metadata or {})
            row.updated_at = run.updated_at
            row.started_at = run.started_at
            row.completed_at = run.completed_at
            session.commit()
            session.refresh(row)
            return _parser_run_to_domain(row)

    def get(self, run_id: str) -> ParserRun | None:
        with self._sf() as session:
            row = session.get(KnowledgeParserRunORM, run_id)
            return _parser_run_to_domain(row) if row else None

    def get_for_source(self, source_id: str) -> ParserRun | None:
        with self._sf() as session:
            row = session.execute(
                select(KnowledgeParserRunORM)
                .where(KnowledgeParserRunORM.source_id == source_id)
                .order_by(KnowledgeParserRunORM.created_at.desc())
            ).scalar_one_or_none()
            return _parser_run_to_domain(row) if row else None

    def list_for_corpus(self, corpus_uuid: str, *, limit: int = 50) -> list[ParserRun]:
        with self._sf() as session:
            rows = session.execute(
                select(KnowledgeParserRunORM)
                .where(KnowledgeParserRunORM.corpus_uuid == corpus_uuid)
                .order_by(KnowledgeParserRunORM.created_at.desc())
                .limit(limit)
            ).scalars().all()
            return [_parser_run_to_domain(row) for row in rows]

    def delete_for_source(self, source_id: str) -> int:
        with self._sf() as session:
            result = session.execute(delete(KnowledgeParserRunORM).where(KnowledgeParserRunORM.source_id == source_id))
            session.commit()
            return int(result.rowcount or 0)

    def delete_for_corpus(self, corpus_uuid: str) -> int:
        with self._sf() as session:
            result = session.execute(delete(KnowledgeParserRunORM).where(KnowledgeParserRunORM.corpus_uuid == corpus_uuid))
            session.commit()
            return int(result.rowcount or 0)


class SQLAlchemyDocumentStore:
    def __init__(self, session_factory) -> None:
        self._sf = session_factory

    def create(self, document: Document) -> Document:
        with self._sf() as session:
            row = KnowledgeDocumentORM(
                id=document.id,
                corpus_uuid=document.corpus_uuid,
                source_id=document.source_id,
                parser_run_id=document.parser_run_id,
                title=document.title,
                language=document.language,
                text_content=document.text_content,
                char_count=document.char_count,
                status=document.status,
                metadata_json=dict(document.metadata or {}),
                created_at=document.created_at,
                updated_at=document.updated_at,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return _document_to_domain(row)

    def update(self, document: Document) -> Document:
        with self._sf() as session:
            row = session.get(KnowledgeDocumentORM, document.id)
            if row is None:
                raise ValueError(f"Document not found: {document.id}")
            row.title = document.title
            row.language = document.language
            row.text_content = document.text_content
            row.char_count = document.char_count
            row.status = document.status
            row.metadata_json = dict(document.metadata or {})
            row.updated_at = document.updated_at
            session.commit()
            session.refresh(row)
            return _document_to_domain(row)

    def get(self, document_id: str) -> Document | None:
        with self._sf() as session:
            row = session.get(KnowledgeDocumentORM, document_id)
            return _document_to_domain(row) if row else None

    def get_for_source(self, source_id: str) -> Document | None:
        with self._sf() as session:
            row = session.execute(select(KnowledgeDocumentORM).where(KnowledgeDocumentORM.source_id == source_id)).scalar_one_or_none()
            return _document_to_domain(row) if row else None

    def delete_for_source(self, source_id: str) -> int:
        with self._sf() as session:
            result = session.execute(delete(KnowledgeDocumentORM).where(KnowledgeDocumentORM.source_id == source_id))
            session.commit()
            return int(result.rowcount or 0)

    def delete_for_corpus(self, corpus_uuid: str) -> int:
        with self._sf() as session:
            result = session.execute(delete(KnowledgeDocumentORM).where(KnowledgeDocumentORM.corpus_uuid == corpus_uuid))
            session.commit()
            return int(result.rowcount or 0)


class SQLAlchemyParagraphStore:
    def __init__(self, session_factory) -> None:
        self._sf = session_factory

    def create_many(self, paragraphs: list[Paragraph]) -> list[Paragraph]:
        if not paragraphs:
            return []
        with self._sf() as session:
            rows = [
                KnowledgeParagraphORM(
                    id=item.id,
                    corpus_uuid=item.corpus_uuid,
                    source_id=item.source_id,
                    document_id=item.document_id,
                    block_id=item.block_id,
                    order_index=item.order_index,
                    text_content=item.text_content,
                    char_start=item.char_start,
                    char_end=item.char_end,
                    sentence_count=item.sentence_count,
                    metadata_json=dict(item.metadata or {}),
                    created_at=item.created_at,
                )
                for item in paragraphs
            ]
            session.add_all(rows)
            session.commit()
            for row in rows:
                session.refresh(row)
            return [_paragraph_to_domain(row) for row in rows]

    def list_for_document(self, document_id: str) -> list[Paragraph]:
        with self._sf() as session:
            rows = session.execute(
                select(KnowledgeParagraphORM)
                .where(KnowledgeParagraphORM.document_id == document_id)
                .order_by(KnowledgeParagraphORM.order_index.asc())
            ).scalars().all()
            return [_paragraph_to_domain(row) for row in rows]

    def delete_for_document(self, document_id: str) -> int:
        with self._sf() as session:
            result = session.execute(delete(KnowledgeParagraphORM).where(KnowledgeParagraphORM.document_id == document_id))
            session.commit()
            return int(result.rowcount or 0)

    def delete_for_corpus(self, corpus_uuid: str) -> int:
        with self._sf() as session:
            result = session.execute(delete(KnowledgeParagraphORM).where(KnowledgeParagraphORM.corpus_uuid == corpus_uuid))
            session.commit()
            return int(result.rowcount or 0)


class SQLAlchemySentenceStore:
    def __init__(self, session_factory) -> None:
        self._sf = session_factory

    def create_many(self, sentences: list[Sentence]) -> list[Sentence]:
        if not sentences:
            return []
        with self._sf() as session:
            rows = [
                KnowledgeSentenceORM(
                    id=item.id,
                    corpus_uuid=item.corpus_uuid,
                    source_id=item.source_id,
                    document_id=item.document_id,
                    paragraph_id=item.paragraph_id,
                    order_index=item.order_index,
                    text_content=item.text_content,
                    char_start=item.char_start,
                    char_end=item.char_end,
                    token_count=item.token_count,
                    metadata_json=dict(item.metadata or {}),
                    created_at=item.created_at,
                )
                for item in sentences
            ]
            session.add_all(rows)
            session.commit()
            for row in rows:
                session.refresh(row)
            return [_sentence_to_domain(row) for row in rows]

    def get(self, sentence_id: str) -> Sentence | None:
        with self._sf() as session:
            row = session.get(KnowledgeSentenceORM, sentence_id)
            return _sentence_to_domain(row) if row else None

    def list_for_document(self, document_id: str) -> list[Sentence]:
        with self._sf() as session:
            rows = session.execute(
                select(KnowledgeSentenceORM)
                .where(KnowledgeSentenceORM.document_id == document_id)
                .order_by(KnowledgeSentenceORM.order_index.asc())
            ).scalars().all()
            return [_sentence_to_domain(row) for row in rows]

    def delete_for_document(self, document_id: str) -> int:
        with self._sf() as session:
            result = session.execute(delete(KnowledgeSentenceORM).where(KnowledgeSentenceORM.document_id == document_id))
            session.commit()
            return int(result.rowcount or 0)

    def delete_for_corpus(self, corpus_uuid: str) -> int:
        with self._sf() as session:
            result = session.execute(delete(KnowledgeSentenceORM).where(KnowledgeSentenceORM.corpus_uuid == corpus_uuid))
            session.commit()
            return int(result.rowcount or 0)


__all__ = [
    "SQLAlchemyDocumentStore",
    "SQLAlchemyParagraphStore",
    "SQLAlchemyParserRunStore",
    "SQLAlchemySentenceStore",
]
