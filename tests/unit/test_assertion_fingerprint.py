from __future__ import annotations

import pytest

from apps.knowledge.application.indexing_pipeline import build_assertion_fingerprint

pytestmark = pytest.mark.unit


def test_assertion_fingerprint_stable_for_same_inputs():
    f1 = build_assertion_fingerprint(
        kb_id=1,
        subject_key="Varga Dániel",
        predicate="dolgozik",
        object_key="AIPLAZA",
        time_bucket="2026-03",
        place_key="budapest",
    )
    f2 = build_assertion_fingerprint(
        kb_id=1,
        subject_key="varga dániel",
        predicate="DOLGOZIK",
        object_key="aiplaza",
        time_bucket="2026-03",
        place_key="Budapest",
    )
    assert f1 == f2
    assert len(f1) == 64


def test_assertion_fingerprint_changes_when_predicate_changes():
    f1 = build_assertion_fingerprint(1, "anna", "dolgozik", "ceg", "2026-03", "budapest")
    f2 = build_assertion_fingerprint(1, "anna", "lakik", "ceg", "2026-03", "budapest")
    assert f1 != f2
