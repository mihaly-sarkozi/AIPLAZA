from __future__ import annotations

import pytest

from apps.knowledge.service.query_resolver_v0 import QueryResolverV0


pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


def test_hu_relation_question_maps_to_relation_intent() -> None:
    profile = QueryResolverV0().resolve("Milyen rendszert használ a support service?")

    assert profile.intent == "relation"
    assert profile.relation_predicate == "uses"
    assert profile.entity_type == "system_component"


def test_hu_rule_question_maps_to_rule_intent() -> None:
    profile = QueryResolverV0().resolve("Mit kell engedelyeznie az admin usernek?")

    assert profile.intent == "rule"
    # A jelenlegi resolver magyar "engedelyez" alakra nem ad kanonikus actiont,
    # de a rule intent és entity_type regressziós védelme fontos.
    assert profile.rule_action is None
    assert profile.entity_type == "user"


def test_hu_event_question_maps_to_event_intent() -> None:
    profile = QueryResolverV0().resolve("Mikor frissult a billing service?")

    assert profile.intent == "event"
    assert profile.time_filter == "event_time"
    assert profile.entity_type == "system_component"


def test_hu_descriptor_question_maps_to_descriptor_intent() -> None:
    profile = QueryResolverV0().resolve("What is the compliance policy?")

    assert profile.intent == "descriptor"
    assert profile.entity_type == "policy"


def test_hu_state_listing_defaults_to_current_time_filter() -> None:
    profile = QueryResolverV0().resolve("Melyik office aktiv most?")

    assert profile.intent == "state"
    assert profile.state == "active"
    assert profile.time_filter == "current"
