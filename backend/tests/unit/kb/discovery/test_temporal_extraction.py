from __future__ import annotations

import pytest

from apps.kb.kb_discovery.dto.DiscoveryChunkDto import DiscoveryChunkDto
from apps.kb.kb_discovery.temporal.DateRecognizer import DateRecognizer

pytestmark = pytest.mark.unit


def test_hungarian_date_extraction():
    recognizer = DateRecognizer()
    chunk = DiscoveryChunkDto(
        chunk_id="c1",
        text="2026. július 1-től érvényes.",
        chunk_type="paragraph",
        order_index=0,
    )
    mentions = recognizer.recognize(chunk)
    assert len(mentions) == 1
    assert mentions[0]["normalized_start"] == "2026-07-01"
