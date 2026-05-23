from __future__ import annotations

import pytest

from apps.knowledge.service.query_resolver_v0 import QueryResolverV0


pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


def test_query_resolver_detects_active_office_listing() -> None:
    profile = QueryResolverV0().resolve("Which offices are active?")

    assert profile.entity_type == "location"
    assert profile.intent == "state"
    assert profile.state == "active"
    assert profile.time_filter == "current"
    assert "active" in profile.keywords
    assert profile.confidence >= 0.75


def test_query_resolver_detects_london_office_historical_state_question() -> None:
    profile = QueryResolverV0().resolve("Was the London office inactive?")

    assert profile.entity_type == "location"
    assert profile.entity == "London office"
    assert profile.intent == "state"
    assert profile.state == "inactive"
    assert profile.time_filter == "historical"
    assert profile.space_filter == "London office"
    assert profile.detected_entities == [
        {"text": "London office", "entity_type": "location", "source": "query_pattern"}
    ]


def test_query_resolver_status_question_does_not_force_time_filter() -> None:
    profile = QueryResolverV0().resolve("What is the status of London office?")

    assert profile.entity_type == "location"
    assert profile.entity == "London office"
    assert profile.intent == "state"
    assert profile.state is None
    assert profile.time_filter is None
    assert "time:no_forced_filter_status_question" in profile.reasons


def test_query_resolver_detects_relation_entity_from_what_does_x_use() -> None:
    profile = QueryResolverV0().resolve("What does the support service use?")

    assert profile.entity_type == "system_component"
    assert profile.entity == "support service"
    assert profile.intent == "relation"
    assert profile.relation_predicate == "uses"
    assert profile.detected_entities == [
        {"text": "support service", "entity_type": "system_component", "source": "query_pattern"}
    ]


def test_query_resolver_detects_relation_entity_from_what_does_x_integrate_with() -> None:
    profile = QueryResolverV0().resolve("What does the support service integrate with?")

    assert profile.entity_type == "system_component"
    assert profile.entity == "support service"
    assert profile.intent == "relation"
    assert profile.relation_predicate == "integrates"


def test_query_resolver_detects_relation_entity_from_which_system_does_x_use() -> None:
    profile = QueryResolverV0().resolve("Which system does the support service use?")

    assert profile.entity_type == "system_component"
    assert profile.entity == "support service"
    assert profile.intent == "relation"
    assert profile.relation_predicate == "uses"


def test_query_resolver_detects_relation_object_queries() -> None:
    services = QueryResolverV0().resolve("Which services integrate with Freshdesk?")
    systems = QueryResolverV0().resolve("Which systems use Freshdesk?")

    assert services.entity_type == "system_component"
    assert services.entity is None
    assert services.intent == "relation"
    assert services.relation_predicate == "integrates"
    assert services.relation_object == "Freshdesk"
    assert systems.entity_type == "system_component"
    assert systems.entity is None
    assert systems.intent == "relation"
    assert systems.relation_predicate == "uses"
    assert systems.relation_object == "Freshdesk"


def test_query_resolver_detects_rule_entity_from_what_must_x_do() -> None:
    profile = QueryResolverV0().resolve("What must the admin user do?")

    assert profile.entity_type == "user"
    assert profile.entity == "admin user"
    assert profile.intent == "rule"
    assert profile.rule_action == "do"


def test_query_resolver_detects_rule_entity_from_what_must_x_enable() -> None:
    profile = QueryResolverV0().resolve("What must the admin user enable?")

    assert profile.entity_type == "user"
    assert profile.entity == "admin user"
    assert profile.intent == "rule"
    assert profile.rule_action == "enable"


def test_query_resolver_detects_rule_entity_from_what_should_x_enable() -> None:
    profile = QueryResolverV0().resolve("What should the admin user enable?")

    assert profile.entity_type == "user"
    assert profile.entity == "admin user"
    assert profile.intent == "rule"
    assert profile.rule_action == "enable"


def test_query_resolver_detects_rule_entity_from_what_is_x_required_to_do() -> None:
    profile = QueryResolverV0().resolve("What is the admin role required to do?")

    assert profile.entity_type == "user"
    assert profile.entity == "admin role"
    assert profile.intent == "rule"
    assert profile.rule_action == "require"


def test_query_resolver_detects_event_entity_from_when_was_x_updated() -> None:
    profile = QueryResolverV0().resolve("When was the billing service updated?")

    assert profile.entity_type == "system_component"
    assert profile.entity == "billing service"
    assert profile.intent == "event"
    assert profile.time_filter == "event_time"


def test_query_resolver_detects_event_entity_from_when_was_x_completed() -> None:
    profile = QueryResolverV0().resolve("When was the security review completed?")

    assert profile.entity_type == "system_component"
    assert profile.entity == "security review"
    assert profile.intent == "event"
    assert profile.time_filter == "event_time"


def test_query_resolver_detects_event_entity_from_what_happened_to_x() -> None:
    profile = QueryResolverV0().resolve("What happened to the security review?")

    assert profile.entity_type == "system_component"
    assert profile.entity == "security review"
    assert profile.intent == "event"
    assert profile.time_filter == "event_time"


def test_query_resolver_detects_event_entity_from_when_did_x_happen() -> None:
    profile = QueryResolverV0().resolve("When did the security review happen?")

    assert profile.entity_type == "system_component"
    assert profile.entity == "security review"
    assert profile.intent == "event"
    assert profile.time_filter == "event_time"


def test_query_resolver_detects_descriptor_question() -> None:
    profile = QueryResolverV0().resolve("Who is Sarah Miller?")

    assert profile.entity == "Sarah Miller"
    assert profile.intent == "descriptor"


def test_query_resolver_detects_policy_applies_to_descriptor_question() -> None:
    profile = QueryResolverV0().resolve("What does the compliance policy apply to?")

    assert profile.entity_type == "policy"
    assert profile.entity == "compliance policy"
    assert profile.intent == "descriptor"


def test_query_resolver_detects_policy_what_is_descriptor_question() -> None:
    profile = QueryResolverV0().resolve("What is the compliance policy?")

    assert profile.entity_type == "policy"
    assert profile.entity == "compliance policy"
    assert profile.intent == "descriptor"


def test_query_resolver_detects_policy_describe_descriptor_question() -> None:
    profile = QueryResolverV0().resolve("What does the compliance policy describe?")

    assert profile.entity_type == "policy"
    assert profile.entity == "compliance policy"
    assert profile.intent == "descriptor"


def test_query_resolver_detects_expected_answer_type_from_hungarian_question_words() -> None:
    resolver = QueryResolverV0()

    assert resolver.resolve("Hol található a London office?").expected_answer_type == "location"
    assert resolver.resolve("Mikor frissült a billing service?").expected_answer_type == "time"
    assert resolver.resolve("Ki felelős a support service-ért?").expected_answer_type == "person"
    assert resolver.resolve("Mit használ a support service?").expected_answer_type == "object"
    assert resolver.resolve("Miért inaktív a London office?").expected_answer_type == "explanation"


def test_query_resolver_adds_hungarian_typo_tolerant_keyword_stems() -> None:
    profile = QueryResolverV0().resolve("nyugdijjakal kapcslatban?")

    assert "nyugdij" in profile.keywords
    assert "kapcslatban" not in profile.keywords


def test_query_resolver_detects_expected_answer_type_from_spanish_question_words() -> None:
    resolver = QueryResolverV0()

    assert resolver.resolve("¿Dónde está la oficina de Madrid?").expected_answer_type == "location"
    assert resolver.resolve("¿Cuándo fue actualizado el billing service?").expected_answer_type == "time"
    assert resolver.resolve("¿Quién es responsable del support service?").expected_answer_type == "person"
