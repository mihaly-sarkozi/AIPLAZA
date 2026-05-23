from __future__ import annotations

import pytest

from apps.knowledge.service.claim_extraction_provenance import infer_extraction_pattern_name

pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


def test_infer_hu_use_object_before_predicate() -> None:
    assert (
        infer_extraction_pattern_name(
            language="hu",
            pred_f="hasznal",
            subject_source="mention",
            display_predicate="használ",
            hu_hasznal_subject_end=10,
        )
        == "hu_use_object_before_predicate"
    )


def test_infer_hu_use_head_subject() -> None:
    assert (
        infer_extraction_pattern_name(
            language="hu",
            pred_f="hasznal",
            subject_source="hu_use_head_heuristic",
            display_predicate="használ",
            hu_hasznal_subject_end=None,
        )
        == "hu_use_head_subject"
    )


def test_infer_en_use_fallback() -> None:
    assert (
        infer_extraction_pattern_name(
            language="en",
            pred_f="uses",
            subject_source="fallback",
            display_predicate="uses",
            hu_hasznal_subject_end=None,
        )
        == "en_use_fallback_subject"
    )
