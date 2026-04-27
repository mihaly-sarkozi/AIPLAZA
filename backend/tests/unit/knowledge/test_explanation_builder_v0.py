from __future__ import annotations

import pytest

from apps.knowledge.service.explanation_builder_v0 import ExplanationBuilderV0


pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


def test_explanation_builder_links_answer_to_claim_sentence_and_source() -> None:
    result = ExplanationBuilderV0().build(
        answer_text="The admin user must enable two-factor authentication.",
        matched_claims=[
            {
                "claim_id": "c-rule",
                "display_claim_text": "admin user must enable two-factor authentication",
                "sentence_ids": ["s-rule"],
                "sentence_text": "The admin user must enable two-factor authentication.",
                "source_ids": ["src-admin"],
            }
        ],
        cited_claim_ids=["c-rule"],
        cited_sentence_ids=["s-rule"],
        cited_source_ids=["src-admin"],
    )

    assert result["answer_text"] == "The admin user must enable two-factor authentication."
    assert result["explanation"]["claims"] == [
        {
            "claim_id": "c-rule",
            "claim_text": "admin user must enable two-factor authentication",
            "sentence_ids": ["s-rule"],
            "source_ids": ["src-admin"],
        }
    ]
    assert result["explanation"]["sentences"] == [
        {
            "sentence_id": "s-rule",
            "sentence_text": "The admin user must enable two-factor authentication.",
            "claim_ids": ["c-rule"],
            "source_ids": ["src-admin"],
        }
    ]
    assert result["explanation"]["sources"] == [
        {
            "source_id": "src-admin",
            "claim_ids": ["c-rule"],
            "sentence_ids": ["s-rule"],
        }
    ]


def test_explanation_builder_uses_only_cited_claims() -> None:
    result = ExplanationBuilderV0().build(
        answer_text="The support service uses Freshdesk.",
        matched_claims=[
            {
                "claim_id": "c-freshdesk",
                "claim_text": "support service uses Freshdesk",
                "sentence_ids": ["s-freshdesk"],
                "source_ids": ["src-support"],
            },
            {
                "claim_id": "c-billing",
                "claim_text": "billing service is active",
                "sentence_ids": ["s-billing"],
                "source_ids": ["src-billing"],
            },
        ],
        cited_claim_ids=["c-freshdesk"],
        cited_sentence_ids=["s-freshdesk"],
        cited_source_ids=["src-support"],
    )

    assert [item["claim_id"] for item in result["explanation"]["claims"]] == ["c-freshdesk"]
    assert [item["source_id"] for item in result["explanation"]["sources"]] == ["src-support"]
