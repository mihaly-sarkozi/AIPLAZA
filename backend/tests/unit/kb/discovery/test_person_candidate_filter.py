from __future__ import annotations

import pytest

from apps.kb.kb_discovery.common.EntityCandidate import EntityCandidate
from apps.kb.kb_discovery.enums.EntityType import EntityType
from apps.kb.kb_discovery.persons.PersonCandidateFilter import PersonCandidateFilter
from apps.kb.kb_discovery.persons.PersonConfidenceScorer import (
    FULL_NAME_BASE_CONFIDENCE,
    GIVEN_NAME_CANDIDATE_CONFIDENCE,
)

pytestmark = pytest.mark.unit


def _candidate(
    *,
    name: str,
    start: int,
    end: int,
    source: str,
    subtype: str | None = None,
    confidence: float = 0.8,
) -> EntityCandidate:
    return EntityCandidate(
        entity_type=EntityType.PERSON,
        name=name,
        normalized_name=name.casefold(),
        chunk_id="c1",
        start_offset=start,
        end_offset=end,
        confidence=confidence,
        source=source,
        subtype=subtype,
    )


def test_full_name_beats_overlapping_single_token_aliases():
    text = "Carlos García aláírta."
    full = _candidate(
        name="Carlos García",
        start=text.index("Carlos"),
        end=text.index("Carlos") + len("Carlos García"),
        source="full_person_name",
        subtype="full_name",
        confidence=FULL_NAME_BASE_CONFIDENCE,
    )
    carlos = _candidate(
        name="Carlos",
        start=text.index("Carlos"),
        end=text.index("Carlos") + len("Carlos"),
        source="person_alias",
        subtype="directory_alias",
    )
    garcia = _candidate(
        name="Garcia",
        start=text.index("García"),
        end=text.index("García") + len("García"),
        source="person_alias",
        subtype="directory_alias",
    )
    result = PersonCandidateFilter().filter([carlos, garcia, full])
    names = {item.name for item in result}
    assert names == {"Carlos García"}


def test_given_name_dropped_when_overlaps_full_name():
    text = "Mihály Sárközi jelent."
    full = _candidate(
        name="Mihály Sárközi",
        start=0,
        end=len("Mihály Sárközi"),
        source="full_person_name",
        subtype="full_name",
        confidence=FULL_NAME_BASE_CONFIDENCE,
    )
    given = _candidate(
        name="Mihály",
        start=0,
        end=len("Mihály"),
        source="given_name",
        subtype="given_name",
        confidence=GIVEN_NAME_CANDIDATE_CONFIDENCE,
    )
    result = PersonCandidateFilter().filter([given, full])
    assert [item.source for item in result] == ["full_person_name"]


def test_non_overlapping_aliases_are_kept():
    text = "Carlos ment. Garcia jött."
    carlos = _candidate(name="Carlos", start=0, end=6, source="person_alias", subtype="directory_alias")
    garcia = _candidate(name="Garcia", start=13, end=19, source="person_alias", subtype="directory_alias")
    result = PersonCandidateFilter().filter([carlos, garcia])
    assert len(result) == 2
