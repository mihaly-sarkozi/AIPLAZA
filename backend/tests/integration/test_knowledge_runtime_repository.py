from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from apps.knowledge.domain.index_build import IndexBuild
from apps.knowledge.domain.query_run import Citation, QueryRun
from apps.knowledge.domain.source import Source
from apps.knowledge.models import KnowledgeIndexBuildORM, KnowledgeQueryRunORM, KnowledgeSourceORM
from apps.knowledge.repositories.knowledge_runtime_repository import (
    SQLAlchemyIndexBuildStore,
    SQLAlchemyQueryRunStore,
    SQLAlchemySourceStore,
)
from core.extensions.tenant.service import install_schema_tables
from core.extensions.tenant.context.tenant_context import current_tenant_schema
from core.kernel.db.session import make_session_factory

_root = Path(__file__).resolve().parent.parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

_env = _root / ".env"
if not _env.exists():
    _env = _root.parent / ".env"
if _env.exists():
    from dotenv import load_dotenv

    load_dotenv(_env)

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module", autouse=True)
def _ensure_demo_schema(ensure_demo_test_tenant, db_engine):
    install_schema_tables(
        db_engine,
        "demo",
        (
            KnowledgeSourceORM.__table__,
            KnowledgeIndexBuildORM.__table__,
            KnowledgeQueryRunORM.__table__,
        ),
    )
    return ensure_demo_test_tenant


def _get_engine() -> Engine | None:
    try:
        from core.kernel.config.config_loader import settings

        url = getattr(settings, "database_url", None) or os.environ.get("DATABASE_URL")
        if not url or "postgresql" not in url.split(":")[0].lower():
            return None
        return create_engine(url, future=True)
    except Exception:
        return None


@pytest.fixture(scope="module")
def db_engine():
    engine = _get_engine()
    if engine is None:
        pytest.skip("Nincs database_url (PostgreSQL)")
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:
        pytest.skip(f"DB nem elérhető: {exc}")
    return engine


@pytest.fixture
def tenant_session_factory():
    from core.kernel.config.config_loader import settings

    token = current_tenant_schema.set("demo")
    try:
        yield make_session_factory(
            settings.database_url,
            pool_pre_ping=getattr(settings, "database_pool_pre_ping", True),
        )
    finally:
        current_tenant_schema.reset(token)


def test_runtime_repositories_persist_source_build_and_query_run(db_engine: Engine, tenant_session_factory) -> None:
    source_store = SQLAlchemySourceStore(tenant_session_factory)
    build_store = SQLAlchemyIndexBuildStore(tenant_session_factory)
    query_run_store = SQLAlchemyQueryRunStore(tenant_session_factory)

    source_id = str(uuid.uuid4())
    build_id = str(uuid.uuid4())
    query_run_id = str(uuid.uuid4())

    try:
        source = source_store.create(
            Source(
                id=source_id,
                tenant="demo",
                corpus_uuid="kb-demo",
                title="Demo source",
                source_type="text",
                raw_content="Pilot RAG source content",
                status="attached",
                created_by=11,
                metadata={"origin": "test"},
            )
        )
        build = build_store.create(
            IndexBuild(
                id=build_id,
                tenant="demo",
                corpus_uuid="kb-demo",
                index_profile_key="basic_chunk_v1",
                status="pending",
                collection_name="kb_demo__basic_chunk_v1",
                created_by=11,
                metadata={"source_count": 1},
            )
        )
        query_run = query_run_store.save(
            QueryRun(
                id=query_run_id,
                tenant="demo",
                query="Mi a pilot RAG?",
                corpus_uuid="kb-demo",
                build_ids=[build_id],
                result_count=1,
                context_text="Pilot context",
                citations=[
                    Citation(
                        source_id=source_id,
                        build_id=build_id,
                        snippet="Pilot RAG source content",
                        score=0.91,
                        title="Demo source",
                    )
                ],
                metadata={"mode": "test"},
            )
        )

        assert source_store.get(source_id) is not None
        assert build_store.get(build_id) is not None
        assert query_run_store.list_recent(corpus_uuid="kb-demo", limit=5)[0].id == query_run.id

        with db_engine.connect() as conn:
            source_row = conn.execute(
                text('SELECT title, status FROM "demo".knowledge_sources WHERE id = :id'),
                {"id": source_id},
            ).first()
            build_row = conn.execute(
                text('SELECT status, chunk_count FROM "demo".knowledge_index_builds WHERE id = :id'),
                {"id": build_id},
            ).first()
            run_row = conn.execute(
                text('SELECT query_text, result_count FROM "demo".knowledge_query_runs WHERE id = :id'),
                {"id": query_run_id},
            ).first()

        assert source_row == ("Demo source", "attached")
        assert build_row == ("pending", 0)
        assert run_row == ("Mi a pilot RAG?", 1)
    finally:
        with db_engine.begin() as conn:
            conn.execute(text('DELETE FROM "demo".knowledge_query_runs WHERE id = :id'), {"id": query_run_id})
            conn.execute(text('DELETE FROM "demo".knowledge_index_builds WHERE id = :id'), {"id": build_id})
            conn.execute(text('DELETE FROM "demo".knowledge_sources WHERE id = :id'), {"id": source_id})
