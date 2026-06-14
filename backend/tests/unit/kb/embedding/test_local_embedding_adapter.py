from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from apps.kb.kb_embedding.adapters.LocalEmbeddingAdapter import LocalEmbeddingAdapter
from apps.kb.kb_embedding.dto.EmbeddingInputDto import EmbeddingInputDto
from apps.kb.kb_embedding.errors.LocalEmbeddingError import LocalEmbeddingError
from apps.kb.kb_embedding.service.GenerateEmbeddingService import GenerateEmbeddingService


def test_local_embedding_adapter_encodes_vectors():
    fake_model = MagicMock()
    fake_model.encode.return_value = np.array([[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]])

    with patch("sentence_transformers.SentenceTransformer", return_value=fake_model):
        adapter = LocalEmbeddingAdapter(
            default_model="BAAI/bge-m3",
            expected_dimension=3,
            batch_size=2,
        )
        vectors = adapter.embed_texts(["hello", "world"], "BAAI/bge-m3")

    assert len(vectors) == 2
    assert len(vectors[0]) == 3
    fake_model.encode.assert_called_once()
    call_kwargs = fake_model.encode.call_args.kwargs
    assert call_kwargs["normalize_embeddings"] is True
    assert call_kwargs["batch_size"] == 2


def test_local_embedding_adapter_empty_input_returns_empty_list():
    adapter = LocalEmbeddingAdapter(default_model="BAAI/bge-m3", expected_dimension=3)
    assert adapter.embed_texts([], "BAAI/bge-m3") == []


def test_local_embedding_adapter_empty_string_safe():
    fake_model = MagicMock()
    fake_model.encode.return_value = np.array([[0.1, 0.2, 0.3]])

    with patch("sentence_transformers.SentenceTransformer", return_value=fake_model):
        adapter = LocalEmbeddingAdapter(default_model="BAAI/bge-m3", expected_dimension=3)
        vectors = adapter.embed_texts(["", "   "], "BAAI/bge-m3")

    assert len(vectors) == 2
    texts_arg = fake_model.encode.call_args.args[0]
    assert texts_arg == [" ", "   "]


def test_local_embedding_adapter_dimension_mismatch_raises():
    fake_model = MagicMock()
    fake_model.encode.return_value = np.array([[0.1, 0.2]])

    with patch("sentence_transformers.SentenceTransformer", return_value=fake_model):
        adapter = LocalEmbeddingAdapter(default_model="BAAI/bge-m3", expected_dimension=3)
        with pytest.raises(LocalEmbeddingError) as exc_info:
            adapter.embed_texts(["text"], "BAAI/bge-m3")

    assert exc_info.value.code == "LOCAL_EMBEDDING_DIMENSION_MISMATCH"


def test_local_embedding_adapter_model_load_failure_raises():
    with patch("sentence_transformers.SentenceTransformer", side_effect=RuntimeError("load failed")):
        adapter = LocalEmbeddingAdapter(default_model="BAAI/bge-m3", expected_dimension=3)
        with pytest.raises(LocalEmbeddingError) as exc_info:
            adapter.embed_texts(["text"], "BAAI/bge-m3")

    assert exc_info.value.code == "LOCAL_EMBEDDING_MODEL_LOAD_FAILED"


def test_generate_service_partial_batch_failure():
    provider = MagicMock()
    provider.ensure_model_loaded = MagicMock()

    def embed_side_effect(texts, model):
        if texts == ["a"]:
            return [[0.1, 0.2, 0.3]]
        raise LocalEmbeddingError("LOCAL_EMBEDDING_GENERATION_FAILED", message="batch failed")

    provider.embed_texts.side_effect = embed_side_effect

    service = GenerateEmbeddingService(
        provider,
        expected_dimension=3,
        batch_size=1,
        local_provider=True,
    )
    inputs = [
        EmbeddingInputDto(
            chunk_id="c1",
            input_text="a",
            input_hash="h1",
            content_hash="ch1",
        ),
        EmbeddingInputDto(
            chunk_id="c2",
            input_text="b",
            input_hash="h2",
            content_hash="ch2",
        ),
    ]
    output = service.generate(inputs, model="BAAI/bge-m3")

    assert len(output.results) == 1
    assert output.results[0].chunk_id == "c1"
    assert len(output.failures) == 1
    assert output.failures[0].chunk_id == "c2"
    assert output.failures[0].error_code == "LOCAL_EMBEDDING_GENERATION_FAILED"

