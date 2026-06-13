from __future__ import annotations

import pytest

from apps.kb.kb_discovery.spatial.LocationRecognizer import LocationRecognizer

pytestmark = pytest.mark.unit


def test_budapesti_iroda_spatial():
    recognizer = LocationRecognizer()
    mentions = recognizer.recognize("a budapesti irodában dolgozunk")
    assert any("irod" in m["raw_text"].lower() for m in mentions)
