from __future__ import annotations

import pytest

from shared.object_storage.s3_compatible import (
    MAX_OBJECT_KEY_LENGTH,
    S3CompatibleObjectStorage,
    sanitize_object_key_part,
)

pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


def _storage_without_client() -> S3CompatibleObjectStorage:
    return object.__new__(S3CompatibleObjectStorage)


@pytest.mark.parametrize("segment", ["", " ", ".", ".."])
def test_sanitize_object_key_part_rejects_empty_or_dot_segments(segment: str) -> None:
    with pytest.raises(ValueError, match="Invalid object key segment"):
        sanitize_object_key_part(segment)


@pytest.mark.parametrize("segment", ["line\nbreak", "tab\tchar", "null\x00byte"])
def test_sanitize_object_key_part_rejects_control_characters(segment: str) -> None:
    with pytest.raises(ValueError, match="control character"):
        sanitize_object_key_part(segment)


@pytest.mark.parametrize("segment", ["a/b", r"a\b"])
def test_sanitize_object_key_part_rejects_path_separators(segment: str) -> None:
    with pytest.raises(ValueError, match="Path separators"):
        sanitize_object_key_part(segment)


def test_build_key_normalizes_slashes_and_joins_validated_segments() -> None:
    storage = _storage_without_client()

    key = storage.build_key(r"tenants\demo", "knowledge", r"runs\run-1", "item-1")

    assert key == "tenants/demo/knowledge/runs/run-1/item-1"


@pytest.mark.parametrize("parts", [("tenants//demo",), ("tenants", "", "demo"), ("tenants", " ", "demo")])
def test_build_key_rejects_empty_segments(parts: tuple[str, ...]) -> None:
    storage = _storage_without_client()

    with pytest.raises(ValueError, match="Invalid object key segment"):
        storage.build_key(*parts)


def test_build_key_rejects_dotdot_segment() -> None:
    storage = _storage_without_client()

    with pytest.raises(ValueError, match="Invalid object key segment"):
        storage.build_key("tenants", "..", "knowledge")


def test_build_key_rejects_over_max_length() -> None:
    storage = _storage_without_client()
    too_long = "a" * (MAX_OBJECT_KEY_LENGTH + 1)

    with pytest.raises(ValueError, match="maximum length"):
        storage.build_key(too_long)
