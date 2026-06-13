from __future__ import annotations

from infra.kb.minio_file_storage import (
    _ascii_metadata_value,
    _ascii_storage_filename,
    _metadata,
)


def test_ascii_storage_filename_preserves_ascii_name() -> None:
    assert _ascii_storage_filename("report.pdf") == "report.pdf"


def test_ascii_storage_filename_hashes_non_ascii_name() -> None:
    original = "Házőrző otthon- és életmód-biztosítás feltételei.pdf"
    safe = _ascii_storage_filename(original)
    assert safe.endswith(".pdf")
    assert safe.encode("ascii")
    assert safe != original


def test_ascii_metadata_value_encodes_non_ascii() -> None:
    encoded = _ascii_metadata_value("Házőrző.pdf")
    assert encoded.startswith("b64url:")
    assert encoded.encode("ascii")


def test_metadata_helper_returns_ascii_values() -> None:
    meta = _metadata(filename="ékezet.pdf", training_item_id="item_123")
    assert all(value.encode("ascii") for value in meta.values())
    assert meta["training_item_id"] == "item_123"
    assert meta["filename"].startswith("b64url:")
