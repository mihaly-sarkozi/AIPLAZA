from __future__ import annotations

import pytest

from apps.knowledge.pii import adapter

pytestmark = pytest.mark.unit


def test_pipeline_cache_reuses_instance_for_same_sensitivity() -> None:
    adapter._pipeline_for_normalized_sensitivity.cache_clear()

    first = adapter._pipeline_for_sensitivity("medium")
    second = adapter._pipeline_for_sensitivity("medium")

    assert first is second


def test_pipeline_cache_normalizes_invalid_sensitivity_to_medium() -> None:
    adapter._pipeline_for_normalized_sensitivity.cache_clear()

    medium_pipeline = adapter._pipeline_for_sensitivity("medium")
    invalid_pipeline = adapter._pipeline_for_sensitivity("unexpected-value")

    assert medium_pipeline is invalid_pipeline
