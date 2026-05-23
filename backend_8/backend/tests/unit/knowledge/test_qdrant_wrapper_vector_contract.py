from __future__ import annotations

import importlib
import sys
import types
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class _FakeEmbeddings:
    def __init__(self, vector: list[float]) -> None:
        self._vector = vector
        self.calls: list[dict[str, object]] = []

    async def create(self, *, model: str, input: str) -> SimpleNamespace:
        self.calls.append({"model": model, "input": input})
        return SimpleNamespace(data=[SimpleNamespace(embedding=list(self._vector))])


class _FakeEmbeddingProvider:
    def __init__(self, vector: list[float], model_key: str = "unit-test-embedding-model", vector_size: int = 1024) -> None:
        self.model_key = model_key
        self.vector_size = vector_size
        self.embeddings = _FakeEmbeddings(vector)

    async def embed_text(self, text: str) -> list[float]:
        response = await self.embeddings.create(model=self.model_key, input=text)
        return list(response.data[0].embedding)

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            vectors.append(await self.embed_text(text))
        return vectors


class _FakeQdrantClient:
    def __init__(self, *, exists: bool = False) -> None:
        self._exists = exists
        self.created_collections: list[dict[str, object]] = []
        self.created_indexes: list[dict[str, object]] = []
        self.upserts: list[dict[str, object]] = []
        self.search_calls: list[dict[str, object]] = []

    def collection_exists(self, *, collection_name: str) -> bool:
        return self._exists

    def create_collection(self, *, collection_name: str, vectors_config) -> None:  # type: ignore[no-untyped-def]
        self.created_collections.append(
            {
                "collection_name": collection_name,
                "vectors_config": vectors_config,
            }
        )
        self._exists = True

    def create_payload_index(self, *, collection_name: str, field_name: str, field_schema) -> None:  # type: ignore[no-untyped-def]
        self.created_indexes.append(
            {
                "collection_name": collection_name,
                "field_name": field_name,
                "field_schema": field_schema,
            }
        )

    def upsert(self, *, collection_name: str, points: list[dict[str, object]]):  # type: ignore[no-untyped-def]
        self.upserts.append({"collection_name": collection_name, "points": points})
        return {"status": "ok"}

    def search(self, **kwargs):  # type: ignore[no-untyped-def]
        self.search_calls.append(kwargs)
        return []


def _import_qdrant_wrapper_class():
    module_names = (
        "qdrant_client",
        "qdrant_client.models",
        "qdrant_client.http.exceptions",
        "openai",
        "core.kernel.config",
        "core.kernel.config.config_loader",
    )
    original_modules = {name: sys.modules.get(name) for name in module_names}
    qdrant_client_module = types.ModuleType("qdrant_client")
    qdrant_client_module.QdrantClient = object
    models_module = types.ModuleType("qdrant_client.models")
    models_module.Distance = types.SimpleNamespace(COSINE="COSINE")
    models_module.PayloadSchemaType = types.SimpleNamespace(
        KEYWORD="KEYWORD",
        INTEGER="INTEGER",
        DATETIME="DATETIME",
    )

    class _VectorParams:
        def __init__(self, size: int, distance) -> None:
            self.size = size
            self.distance = distance

    class _FieldCondition:
        def __init__(self, key=None, match=None, range=None) -> None:
            self.key = key
            self.match = match
            self.range = range

    class _MatchAny:
        def __init__(self, any=None) -> None:
            self.any = any

    class _MatchValue:
        def __init__(self, value=None) -> None:
            self.value = value

    class _Range:
        def __init__(self, gte=None, lte=None, gt=None, lt=None) -> None:
            self.gte = gte
            self.lte = lte
            self.gt = gt
            self.lt = lt

    class _Filter:
        def __init__(self, must=None) -> None:
            self.must = must or []

    models_module.VectorParams = _VectorParams
    models_module.FieldCondition = _FieldCondition
    models_module.MatchAny = _MatchAny
    models_module.MatchValue = _MatchValue
    models_module.Range = _Range
    models_module.Filter = _Filter
    qdrant_client_module.models = models_module

    http_exc_module = types.ModuleType("qdrant_client.http.exceptions")

    class _ResponseHandlingException(Exception):
        pass

    class _UnexpectedResponse(Exception):
        def __init__(self, status_code: int = 500):
            self.status_code = status_code
            super().__init__(f"status={status_code}")

    http_exc_module.ResponseHandlingException = _ResponseHandlingException
    http_exc_module.UnexpectedResponse = _UnexpectedResponse

    openai_module = types.ModuleType("openai")
    openai_module.AsyncOpenAI = object

    config_loader_module = types.ModuleType("core.kernel.config.config_loader")
    qdrant_settings = types.SimpleNamespace(
        qdrant_lexical_overlap_weight=0.72,
        qdrant_lexical_substring_weight=0.28,
        qdrant_fusion_semantic_weight=0.72,
        qdrant_fusion_lexical_weight=0.28,
    )
    config_loader_module.settings = qdrant_settings
    config_loader_module.get_settings = lambda: qdrant_settings
    config_loader_module.get_app_env = lambda: "dev"
    config_module = types.ModuleType("core.kernel.config")
    config_module.settings = qdrant_settings
    config_module.get_settings = lambda: qdrant_settings
    config_module.get_app_env = lambda: "dev"

    try:
        sys.modules["qdrant_client"] = qdrant_client_module
        sys.modules["qdrant_client.models"] = models_module
        sys.modules["qdrant_client.http.exceptions"] = http_exc_module
        sys.modules["openai"] = openai_module
        sys.modules["core.kernel.config"] = config_module
        sys.modules["core.kernel.config.config_loader"] = config_loader_module
        module = importlib.import_module("apps.knowledge.qdrant.qdrant_wrapper")
    finally:
        for name, original in original_modules.items():
            if original is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = original
    return module.QdrantClientWrapper


def _build_wrapper(*, client: _FakeQdrantClient, embedding_vector: list[float] | None = None):
    wrapper_cls = _import_qdrant_wrapper_class()
    wrapper = object.__new__(wrapper_cls)
    wrapper.client = client
    wrapper.embedding_provider = _FakeEmbeddingProvider(embedding_vector or [0.1, 0.2, 0.3])
    wrapper.embedding_model = "unit-test-embedding-model"
    wrapper.vector_size = 1024
    wrapper._embedding_cache = {}
    wrapper._embedding_cache_order = []
    wrapper._embedding_cache_max = 64
    return wrapper


def test_ensure_collection_schema_creates_collection_with_explicit_vector_size() -> None:
    client = _FakeQdrantClient(exists=False)
    wrapper = _build_wrapper(client=client)

    wrapper.ensure_collection_schema("kb_contract_test", vector_size=1024)

    assert len(client.created_collections) == 1
    created = client.created_collections[0]
    assert created["collection_name"] == "kb_contract_test"
    assert getattr(created["vectors_config"], "size") == 1024
    assert client.created_indexes


@pytest.mark.anyio
async def test_ensure_collection_schema_async_forwards_vector_size() -> None:
    client = _FakeQdrantClient(exists=True)
    wrapper = _build_wrapper(client=client)
    calls: list[tuple[str, int | None]] = []

    def _ensure(collection_name: str, vector_size: int | None = None, _distance=None) -> None:
        calls.append((collection_name, vector_size))

    wrapper.ensure_collection_schema = _ensure  # type: ignore[method-assign]

    await wrapper.ensure_collection_schema_async("kb_async_contract", vector_size=2048)

    assert calls == [("kb_async_contract", 2048)]


@pytest.mark.anyio
async def test_upsert_sentence_points_embeds_when_vector_missing() -> None:
    client = _FakeQdrantClient(exists=False)
    wrapper = _build_wrapper(client=client, embedding_vector=[0.4, 0.5, 0.6])

    await wrapper.upsert_sentence_points(
        "kb_sentence_contract",
        [
            {
                "id": "sentence-1",
                "text": "  Ez egy teszt mondat.  ",
                "payload": {"source_id": "src-1"},
            }
        ],
    )

    assert len(client.upserts) == 1
    point = client.upserts[0]["points"][0]
    assert point["vector"] == [0.4, 0.5, 0.6]
    assert point["payload"]["point_type"] == "sentence"
    assert point["payload"]["text"] == "Ez egy teszt mondat."
    assert wrapper.embedding_provider.embeddings.calls[0]["input"] == "Ez egy teszt mondat."


@pytest.mark.anyio
async def test_search_points_uses_precomputed_query_vector_without_embedding() -> None:
    client = _FakeQdrantClient(exists=True)
    wrapper = _build_wrapper(client=client)
    wrapper.embed_text = AsyncMock(side_effect=AssertionError("embed_text should not be called"))  # type: ignore[method-assign]
    expected_vector = [0.9, 0.8, 0.7]

    rows = await wrapper.search_points(
        collection="kb_query_contract",
        query="ignored query",
        query_vector=expected_vector,
        limit=3,
    )

    assert rows == []
    assert len(client.search_calls) == 1
    assert client.search_calls[0]["query_vector"] == expected_vector
    assert wrapper.embed_text.await_count == 0


@pytest.mark.anyio
async def test_search_points_embeds_query_when_query_vector_missing() -> None:
    client = _FakeQdrantClient(exists=True)
    wrapper = _build_wrapper(client=client)
    wrapper.embed_text = AsyncMock(return_value=[0.11, 0.12, 0.13])  # type: ignore[method-assign]

    rows = await wrapper.search_points(
        collection="kb_query_contract",
        query="Mikor frissult a billing service?",
        limit=5,
    )

    assert rows == []
    wrapper.embed_text.assert_awaited_once_with("Mikor frissult a billing service?")
    assert client.search_calls[0]["query_vector"] == [0.11, 0.12, 0.13]
