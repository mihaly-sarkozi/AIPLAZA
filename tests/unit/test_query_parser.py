from __future__ import annotations

import pytest
from datetime import datetime

from apps.knowledge.application.query_parser import QueryParser

pytestmark = pytest.mark.unit


def test_query_parser_extracts_entities_time_place():
    parser = QueryParser()
    parsed = parser.parse("Mi történt 2024-ben Budapest városban Varga Dániellel?")
    assert parsed["intent"] == "activity"
    assert "2024" in parsed["time_candidates"]
    assert any("Budapest" == x for x in parsed["place_candidates"])
    assert any("Varga" in x or "Dániellel" in x for x in parsed["entity_candidates"])


def test_query_parser_detects_predicate_candidate():
    parser = QueryParser()
    parsed = parser.parse("Ki dolgozik az AIPLAZA projektben?")
    assert "dolgozik" in parsed["predicate_candidates"]


def test_query_parser_handles_relative_time_keywords():
    parser = QueryParser()
    parsed = parser.parse("Mi történt tavaly Budapesten?")
    now = datetime.utcnow()
    assert parsed["query_time_from"] is not None
    assert parsed["query_time_from"].year == now.year - 1


def test_query_parser_handles_hungarian_month_word():
    parser = QueryParser()
    parsed = parser.parse("Mi történt 2024 február időszakban?")
    assert parsed["query_time_from"] is not None
    assert parsed["query_time_from"].year == 2024
    assert parsed["query_time_from"].month == 2
