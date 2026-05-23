from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from apps.knowledge.domain.index_build import IndexBuild
from apps.knowledge.models import KnowledgeIndexBuildORM
from apps.knowledge.repositories.knowledge_runtime_repository import SQLAlchemyIndexBuildStore
from core.modules.tenant.context.tenant_context import current_tenant_schema
from core.modules.tenant.service import install_schema_tables
from core.kernel.db.session import make_session_factory


pytestmark = [pytest.mark.integration, pytest.mark.must_pass]


@pytest.fixture(scope="module")
def qdrant_client():
    qdrant = pytest.importorskip("qdrant_client")
    qm = pytest.importorskip("qdrant_client.models")
    url = os.getenv("QDRANT_URL", "http://localhost:6333")
    api_key = (os.getenv("QDRANT_API_KEY") or "").strip() or None
    client = qdrant.QdrantClient(url=url, api_key=api_key, check_compatibility=False)
    try:
        client.get_collections()
    except Exception as exc:  # pragma: no cover - env dependent
        pytest.skip(f"Qdrant nem elérhető storage consistency teszthez: {exc}")
    return client, qm


@pytest.fixture(scope="module")
def db_engine() -> Engine:
    from core.kernel.config.config_loader import settings

    engine = create_engine(settings.database_url, future=True)
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return engine


@pytest.fixture(scope="module", autouse=True)
def ensure_schema(ensure_demo_test_tenant, db_engine: Engine):
    install_schema_tables(
        db_engine,
        "demo",
        (
            KnowledgeIndexBuildORM.__table__,
        ),
    )
    return ensure_demo_test_tenant


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


def test_storage_consistency_for_ready_index_build(db_engine: Engine, tenant_session_factory, qdrant_client) -> None:
    client, qm = qdrant_client
    build_store = SQLAlchemyIndexBuildStore(tenant_session_factory)
    build_id = str(uuid.uuid4())
    collection_name = f"kb_storage_contract_{uuid.uuid4().hex[:10]}"

    try:
        if client.collection_exists(collection_name=collection_name):
            client.delete_collection(collection_name=collection_name)
        client.create_collection(
            collection_name=collection_name,
            vectors_config=qm.VectorParams(size=3, distance=qm.Distance.COSINE),
        )
        client.upsert(
            collection_name=collection_name,
            points=[
                qm.PointStruct(
                    id=1,
                    vector=[0.1, 0.2, 0.3],
                    payload={
                        "build_id": build_id,
                        "index_profile_key": "hybrid_v1",
                        "source_id": "src-1",
                        "point_type": "sentence",
                    },
                )
            ],
        )

        created = build_store.create(
            IndexBuild(
                id=build_id,
                tenant="demo",
                corpus_uuid="kb-demo",
                index_profile_key="hybrid_v1",
                status="ready",
                collection_name=collection_name,
                chunk_count=1,
                metadata={"source_count": 1},
            )
        )
        assert created.status == "ready"
        assert created.chunk_count == 1

        with db_engine.connect() as conn:
            row = conn.execute(
                text('SELECT status, chunk_count, index_profile_key FROM "demo".knowledge_index_builds WHERE id = :id'),
                {"id": build_id},
            ).first()
        assert row == ("ready", 1, "hybrid_v1")

        counted = client.count(collection_name=collection_name, count_filter=None, exact=True)
        assert int(counted.count) == 1
    finally:
        with db_engine.begin() as conn:
            conn.execute(text('DELETE FROM "demo".knowledge_index_builds WHERE id = :id'), {"id": build_id})
        try:
            client.delete_collection(collection_name=collection_name)
        except Exception:
            pass
