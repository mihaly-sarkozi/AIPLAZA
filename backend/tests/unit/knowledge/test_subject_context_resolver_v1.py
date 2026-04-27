from __future__ import annotations

from apps.knowledge.domain.claim import Claim
from apps.knowledge.service.knowledge_trace_service import _trace_claim_extraction_fields
from apps.knowledge.service.subject_context_resolver_v1 import SubjectContextResolverV1


def test_subject_context_carries_implicit_subject_second_sentence_dict() -> None:
    r = SubjectContextResolverV1().resolve_claims(
        [
            {
                "sentence_id": "s1",
                "order_index": 0,
                "text": "Kiss Márton a Zalka 2000 compliance vezetője.",
                "language": "hu",
                "claims": [
                    {
                        "id": "c1",
                        "subject_text": "Kiss Márton",
                        "predicate_text": "vezetője",
                        "object_text": "Zalka 2000 compliance",
                    }
                ],
            },
            {
                "sentence_id": "s2",
                "order_index": 1,
                "text": "Korábban a belső audit folyamatért felelt.",
                "language": "hu",
                "claims": [
                    {
                        "id": "c2",
                        "subject_text": "",
                        "predicate_text": "felelt",
                        "object_text": "a belső audit folyamatért",
                    }
                ],
            },
        ]
    )
    assert r[0]["claims"][0]["context_subject_applied"] is False
    assert r[0]["claims"][0]["context_subject_reason"] == "no_strong_anchor_in_previous_two_sentences"
    c2 = r[1]["claims"][0]
    assert c2["subject_text"] == "Kiss Márton"
    assert c2["context_subject_applied"] is True
    assert c2["context_subject_source_sentence_id"] == "s1"
    assert c2["context_subject_source_claim_id"] == "c1"
    assert c2["context_subject_source_subject"] == "Kiss Márton"
    assert c2["context_subject_reason"] == "implicit_subject"


def test_subject_context_keeps_explicit_subject_when_valid() -> None:
    r = SubjectContextResolverV1().resolve_claims(
        [
            {
                "sentence_id": "s1",
                "order_index": 0,
                "text": "Kiss Márton a Zalka 2000 compliance vezetője.",
                "language": "hu",
                "claims": [
                    {
                        "id": "c1",
                        "subject_text": "Kiss Márton",
                        "predicate_text": "vezetője",
                        "object_text": "Zalka 2000 compliance",
                    }
                ],
            },
            {
                "sentence_id": "s2",
                "order_index": 1,
                "text": "Nagy Péter a belső audit folyamatért felelt.",
                "language": "hu",
                "claims": [
                    {
                        "id": "c2",
                        "subject_text": "Nagy Péter",
                        "predicate_text": "felelt",
                        "object_text": "a belső audit folyamatért",
                    }
                ],
            },
        ]
    )
    c2 = r[1]["claims"][0]
    assert c2["subject_text"] == "Nagy Péter"
    assert c2["context_subject_applied"] is False
    assert c2["context_subject_reason"] == "explicit_subject_kept"


def test_subject_context_does_not_overwrite_explicit_billing_service_after_location_sentence() -> None:
    r = SubjectContextResolverV1().resolve_claims(
        [
            {
                "sentence_id": "s1",
                "order_index": 0,
                "text": "A Budapesti iroda jelenleg aktív támogatási központ.",
                "language": "hu",
                "claims": [
                    {
                        "id": "c1",
                        "subject_text": "Budapesti iroda",
                        "predicate_text": "aktív",
                        "object_text": "támogatási központ",
                    }
                ],
            },
            {
                "sentence_id": "s2",
                "order_index": 1,
                "text": "A billing service jelenleg Stripe rendszert használ kártyás fizetésekhez.",
                "language": "hu",
                "claims": [
                    {
                        "id": "c2",
                        "subject_text": "billing service",
                        "predicate_text": "használ",
                        "object_text": "Stripe rendszert",
                    }
                ],
            },
        ]
    )
    c2 = r[1]["claims"][0]
    assert c2["subject_text"] == "billing service"
    assert c2["context_subject_applied"] is False
    assert c2["context_subject_reason"] == "explicit_subject_kept"


def test_subject_context_claim_objects_and_trace_metadata_fields() -> None:
    c1 = Claim(
        id="c1",
        sentence_id="s1",
        subject_text="Kiss Márton",
        predicate_text="vezetője",
        object_text="Zalka 2000 compliance",
        metadata={"language": "hu"},
    )
    c2 = Claim(
        id="c2",
        sentence_id="s2",
        subject_text="",
        predicate_text="felelt",
        object_text="a belső audit folyamatért",
        metadata={"language": "hu"},
    )
    r = SubjectContextResolverV1().resolve_claims(
        [
            {"sentence_id": "s1", "order_index": 0, "text": "Kiss Márton a Zalka 2000 compliance vezetője.", "language": "hu", "claims": [c1]},
            {"sentence_id": "s2", "order_index": 1, "text": "Korábban a belső audit folyamatért felelt.", "language": "hu", "claims": [c2]},
        ]
    )
    out = r[1]["claims"][0]
    assert isinstance(out, Claim)
    assert out.subject_text == "Kiss Márton"
    assert out.metadata.get("context_subject_applied") is True
    assert out.metadata.get("context_subject_source_claim_id") == "c1"
    fields = _trace_claim_extraction_fields(out)
    assert fields.get("context_subject_applied") is True
    assert fields.get("context_subject_source_sentence_id") == "s1"
    assert fields.get("subject_source") == "carryover"
    assert fields.get("carryover_from_sentence_id") == "s1"


def test_subject_context_chain_second_implicit_without_reanchor_in_text() -> None:
    """Az explicit horgony legfeljebb 2 mondat távolságra érvényes (közbeeső implicit mondatokkal)."""
    r = SubjectContextResolverV1().resolve_claims(
        [
            {
                "sentence_id": "s1",
                "order_index": 0,
                "text": "Kiss Márton a Zalka 2000 compliance vezetője.",
                "language": "hu",
                "claims": [{"id": "c1", "subject_text": "Kiss Márton", "predicate_text": "vezetője", "object_text": "Zalka 2000 compliance"}],
            },
            {
                "sentence_id": "s2",
                "order_index": 1,
                "text": "Korábban a belső audit folyamatért felelt.",
                "language": "hu",
                "claims": [{"id": "c2", "subject_text": "", "predicate_text": "felelt", "object_text": "a belső audit folyamatért"}],
            },
            {
                "sentence_id": "s3",
                "order_index": 2,
                "text": "Ezt követően a jogszerűségi ellenőrzéseket koordinálta.",
                "language": "hu",
                "claims": [{"id": "c3", "subject_text": "", "predicate_text": "koordinálta", "object_text": "a jogszerűségi ellenőrzéseket"}],
            },
        ]
    )
    assert r[2]["claims"][0]["subject_text"] == "Kiss Márton"
    assert r[2]["claims"][0]["context_subject_applied"] is True
    assert r[2]["claims"][0]["context_subject_source_claim_id"] == "c1"


def test_subject_context_no_carry_beyond_two_sentence_window() -> None:
    """A 4. mondatnál már nincs érvényes horgony (a gyökér explicit +2 mondatnál messzebb)."""
    r = SubjectContextResolverV1().resolve_claims(
        [
            {
                "sentence_id": "s1",
                "order_index": 0,
                "text": "Kiss Márton a Zalka 2000 compliance vezetője.",
                "language": "hu",
                "claims": [{"id": "c1", "subject_text": "Kiss Márton", "predicate_text": "vezetője", "object_text": "Zalka 2000 compliance"}],
            },
            {
                "sentence_id": "s2",
                "order_index": 1,
                "text": "Korábban a belső audit folyamatért felelt.",
                "language": "hu",
                "claims": [{"id": "c2", "subject_text": "", "predicate_text": "felelt", "object_text": "a belső audit folyamatért"}],
            },
            {
                "sentence_id": "s3",
                "order_index": 2,
                "text": "Ezt követően a jogszerűségi ellenőrzéseket koordinálta.",
                "language": "hu",
                "claims": [{"id": "c3", "subject_text": "", "predicate_text": "koordinálta", "object_text": "a jogszerűségi ellenőrzéseket"}],
            },
            {
                "sentence_id": "s4",
                "order_index": 3,
                "text": "Később a jelentések határidejét is felügyelte.",
                "language": "hu",
                "claims": [{"id": "c4", "subject_text": "", "predicate_text": "felügyelte", "object_text": "a jelentések határidejét"}],
            },
        ]
    )
    c4 = r[3]["claims"][0]
    assert c4["context_subject_applied"] is False
    assert c4["context_subject_reason"] == "no_strong_anchor_in_previous_two_sentences"
    assert c4["subject_text"] == ""


def test_subject_context_skips_question_sentence() -> None:
    r = SubjectContextResolverV1().resolve_claims(
        [
            {
                "sentence_id": "s1",
                "order_index": 0,
                "text": "Kiss Márton a Zalka 2000 compliance vezetője.",
                "language": "hu",
                "claims": [{"id": "c1", "subject_text": "Kiss Márton", "predicate_text": "vezetője", "object_text": "Zalka 2000 compliance"}],
            },
            {
                "sentence_id": "s2",
                "order_index": 1,
                "text": "Ki felelt korábban a belső audit folyamatért?",
                "language": "hu",
                "claims": [{"id": "c2", "subject_text": "", "predicate_text": "felelt", "object_text": "a belső audit folyamatért"}],
            },
        ]
    )
    c2 = r[1]["claims"][0]
    assert c2["context_subject_applied"] is False
    assert "sentence_is_question" in c2["context_subject_reason"]


def test_intermediate_explicit_location_replaces_person_for_next_carry() -> None:
    """Új erős location subject felülírja a kontextust; felelősségi targetre nem kompatibilis."""
    r = SubjectContextResolverV1().resolve_claims(
        [
            {
                "sentence_id": "s1",
                "order_index": 0,
                "text": "Kiss Márton a compliance vezetője.",
                "language": "hu",
                "claims": [
                    {"id": "c1", "subject_text": "Kiss Márton", "predicate_text": "vezetője", "object_text": "compliance"}
                ],
            },
            {
                "sentence_id": "s2",
                "order_index": 1,
                "text": "The London office is active.",
                "language": "en",
                "claims": [{"id": "c2", "subject_text": "London office", "predicate_text": "is", "object_text": "active"}],
            },
            {
                "sentence_id": "s3",
                "order_index": 2,
                "text": "Korábban auditért felelt.",
                "language": "hu",
                "claims": [{"id": "c3", "subject_text": "", "predicate_text": "felelt", "object_text": "auditért"}],
            },
        ]
    )
    c3 = r[2]["claims"][0]
    assert c3["context_subject_applied"] is False
    assert "kiss" not in (c3.get("subject_text") or "").lower()
    assert "london" not in (c3.get("subject_text") or "").lower()
    assert c3.get("context_subject_reason") == "incompatible_subject_context:location"


def test_weak_subject_hu_object_like_phrase_is_replaced() -> None:
    """„belső audit folyamatért” típusú tárgy-szerű subject gyenge → átveszi a horgonyt."""
    r = SubjectContextResolverV1().resolve_claims(
        [
            {
                "sentence_id": "s1",
                "order_index": 0,
                "text": "Kiss Márton a Zalka 2000 compliance vezetője.",
                "language": "hu",
                "claims": [{"id": "c1", "subject_text": "Kiss Márton", "predicate_text": "vezetője", "object_text": "Zalka 2000 compliance"}],
            },
            {
                "sentence_id": "s2",
                "order_index": 1,
                "text": "Korábban a belső audit folyamatért felelt.",
                "language": "hu",
                "claims": [
                    {
                        "id": "c2",
                        "subject_text": "belső audit folyamatért",
                        "predicate_text": "felelt",
                        "object_text": "",
                    }
                ],
            },
        ]
    )
    c2 = r[1]["claims"][0]
    assert c2["subject_text"] == "Kiss Márton"
    assert c2["context_subject_applied"] is True
    assert c2["context_subject_reason"] == "weak_subject_override"


def test_weak_subject_general_pronoun_token_replaced() -> None:
    r = SubjectContextResolverV1().resolve_claims(
        [
            {
                "sentence_id": "s1",
                "order_index": 0,
                "text": "Kiss Márton a Zalka 2000 compliance vezetője.",
                "language": "hu",
                "claims": [{"id": "c1", "subject_text": "Kiss Márton", "predicate_text": "vezetője", "object_text": "Zalka 2000 compliance"}],
            },
            {
                "sentence_id": "s2",
                "order_index": 1,
                "text": "Ő korábban a belső audit folyamatért felelt.",
                "language": "hu",
                "claims": [{"id": "c2", "subject_text": "ő", "predicate_text": "felelt", "object_text": "a belső audit folyamatért"}],
            },
        ]
    )
    assert r[1]["claims"][0]["subject_text"] == "Kiss Márton"
    assert r[1]["claims"][0]["context_subject_applied"] is True
    assert r[1]["claims"][0]["context_subject_reason"] == "weak_subject_override"


def test_subject_context_blocks_new_person_mention_near_start() -> None:
    r = SubjectContextResolverV1().resolve_claims(
        [
            {
                "sentence_id": "s1",
                "order_index": 0,
                "text": "Kiss Márton a Zalka 2000 compliance vezetője.",
                "language": "hu",
                "claims": [{"id": "c1", "subject_text": "Kiss Márton", "predicate_text": "vezetője", "object_text": "Zalka 2000 compliance"}],
            },
            {
                "sentence_id": "s2",
                "order_index": 1,
                "text": "Nagy Péter korábban a belső audit folyamatért felelt.",
                "language": "hu",
                "mentions": [
                    {"mention_id": "m1", "surface_text": "Nagy Péter", "mention_type": "person", "char_start": 0, "char_end": 10},
                ],
                "claims": [{"id": "c2", "subject_text": "", "predicate_text": "felelt", "object_text": "a belső audit folyamatért"}],
            },
        ]
    )
    c2 = r[1]["claims"][0]
    assert c2["context_subject_applied"] is False
    assert "new_explicit_entity" in c2["context_subject_reason"]


def test_subject_context_allows_organization_anchor_from_company_mention() -> None:
    r = SubjectContextResolverV1().resolve_claims(
        [
            {
                "sentence_id": "s1",
                "order_index": 0,
                "text": "Zalka 2000 adatvédelmi rendszerrel dolgozik.",
                "language": "hu",
                "mentions": [
                    {"mention_id": "m1", "surface_text": "Zalka 2000", "mention_type": "company", "char_start": 0, "char_end": 10}
                ],
                "claims": [
                    {
                        "id": "c1",
                        "subject_text": "Zalka 2000",
                        "subject_mention_id": "m1",
                        "predicate_text": "dolgozik",
                        "object_text": "adatvédelmi rendszerrel",
                    }
                ],
            },
            {
                "sentence_id": "s2",
                "order_index": 1,
                "text": "Később audit modulhoz kapcsolódik.",
                "language": "hu",
                "claims": [
                    {
                        "id": "c2",
                        "subject_text": "",
                        "predicate_text": "kapcsolódik",
                        "object_text": "audit modulhoz",
                    }
                ],
            },
        ]
    )

    c2 = r[1]["claims"][0]
    assert c2["subject_text"] == "Zalka 2000"
    assert c2["context_subject_applied"] is True
    assert c2["context_subject_reason"] == "implicit_subject"


def test_subject_context_skips_when_previous_subject_type_is_not_allowed() -> None:
    r = SubjectContextResolverV1().resolve_claims(
        [
            {
                "sentence_id": "s1",
                "order_index": 0,
                "text": "Belső audit folyamat kötelező.",
                "language": "hu",
                "mentions": [
                    {
                        "mention_id": "m1",
                        "surface_text": "Belső audit folyamat",
                        "mention_type": "process",
                        "char_start": 0,
                        "char_end": 21,
                    }
                ],
                "claims": [
                    {
                        "id": "c1",
                        "subject_text": "Belső audit folyamat",
                        "subject_mention_id": "m1",
                        "predicate_text": "kötelező",
                        "object_text": None,
                    }
                ],
            },
            {
                "sentence_id": "s2",
                "order_index": 1,
                "text": "Korábban a jelentésekért felelt.",
                "language": "hu",
                "claims": [{"id": "c2", "subject_text": "", "predicate_text": "felelt", "object_text": "jelentésekért"}],
            },
        ]
    )

    c2 = r[1]["claims"][0]
    assert c2["subject_text"] == ""
    assert c2["context_subject_applied"] is False
    assert c2["context_subject_reason"] == "no_strong_anchor_in_previous_two_sentences"


def test_subject_context_en_previous_responsible_weak_subject_gets_person_anchor() -> None:
    r = SubjectContextResolverV1().resolve_claims(
        [
            {
                "sentence_id": "s1",
                "order_index": 0,
                "text": "Sarah Miller is the compliance lead at Zalka 2000.",
                "language": "en",
                "claims": [
                    {"id": "c1", "subject_text": "Sarah Miller", "predicate_text": "is", "object_text": "compliance lead at Zalka 2000"}
                ],
            },
            {
                "sentence_id": "s2",
                "order_index": 1,
                "text": "Previously responsible for the internal audit process.",
                "language": "en",
                "claims": [
                    {
                        "id": "c2",
                        "subject_text": "Previously responsible",
                        "predicate_text": "responsible",
                        "object_text": "for the internal audit process",
                    }
                ],
            },
        ]
    )
    c2 = r[1]["claims"][0]
    assert c2["subject_text"] == "Sarah Miller"
    assert c2["context_subject_applied"] is True
    assert c2["context_subject_reason"] == "weak_subject_override"


def test_subject_context_en_state_weak_subject_gets_location_anchor() -> None:
    r = SubjectContextResolverV1().resolve_claims(
        [
            {
                "sentence_id": "s1",
                "order_index": 0,
                "text": "The London office is currently active.",
                "language": "en",
                "claims": [{"id": "c1", "subject_text": "London office", "predicate_text": "is active", "object_text": None}],
            },
            {
                "sentence_id": "s2",
                "order_index": 1,
                "text": "Was inactive before March 2025.",
                "language": "en",
                "claims": [{"id": "c2", "subject_text": "Was inactive", "predicate_text": "Was inactive", "object_text": "before March 2025"}],
            },
        ]
    )
    c2 = r[1]["claims"][0]
    assert c2["subject_text"] == "London office"
    assert c2["predicate_text"] == "was inactive"
    assert c2["context_subject_applied"] is True
    assert c2["context_subject_reason"] == "weak_subject_override"


def test_stress_pronoun_work_relation_and_it_state_use_safe_anchors() -> None:
    r = SubjectContextResolverV1().resolve_claims(
        [
            {
                "sentence_id": "s1",
                "order_index": 0,
                "text": "Alice is the data protection lead at Acme Corp.",
                "language": "en",
                "claims": [
                    {
                        "id": "c1",
                        "subject_text": "Alice",
                        "predicate_text": "data protection lead at",
                        "object_text": "Acme Corp",
                    }
                ],
            },
            {
                "sentence_id": "s2",
                "order_index": 1,
                "text": "She works in the London office.",
                "language": "en",
                "claims": [
                    {
                        "id": "c2",
                        "subject_text": "",
                        "predicate_text": "works",
                        "object_text": "in the London office",
                    }
                ],
            },
            {
                "sentence_id": "s3",
                "order_index": 2,
                "text": "It was active before January 2025.",
                "language": "en",
                "claims": [
                    {
                        "id": "c3",
                        "subject_text": "",
                        "predicate_text": "was active",
                        "object_text": "before January 2025",
                    }
                ],
            },
        ]
    )

    c2 = r[1]["claims"][0]
    c3 = r[2]["claims"][0]
    assert c2["subject_text"] == "Alice"
    assert c2["context_subject_applied"] is True
    assert c2["context_subject_sentence_pattern_id"] == "en_she_works_in"
    assert c3["subject_text"] == "London office"
    assert c3["context_subject_applied"] is True
    assert c3["context_subject_source_subject"] == "London office"


def test_subject_context_es_anteriormente_fue_weak_subject_gets_person_anchor() -> None:
    r = SubjectContextResolverV1().resolve_claims(
        [
            {
                "sentence_id": "s1",
                "order_index": 0,
                "text": "Carlos García es el responsable de compliance en Zalka 2000.",
                "language": "es",
                "claims": [
                    {
                        "id": "c1",
                        "subject_text": "Carlos García",
                        "predicate_text": "es",
                        "object_text": "responsable de compliance en Zalka 2000",
                    }
                ],
            },
            {
                "sentence_id": "s2",
                "order_index": 1,
                "text": "Anteriormente fue responsable del proceso de auditoría interna.",
                "language": "es",
                "claims": [
                    {
                        "id": "c2",
                        "subject_text": "Anteriormente fue",
                        "predicate_text": "fue",
                        "object_text": "responsable del proceso de auditoría interna",
                    }
                ],
            },
        ]
    )
    c2 = r[1]["claims"][0]
    assert c2["subject_text"] == "Carlos García"
    assert c2["context_subject_applied"] is True
    assert c2["context_subject_reason"] == "weak_subject_override"


def test_subject_context_es_state_weak_subject_gets_location_anchor() -> None:
    r = SubjectContextResolverV1().resolve_claims(
        [
            {
                "sentence_id": "s1",
                "order_index": 0,
                "text": "La oficina de Madrid está actualmente activa.",
                "language": "es",
                "claims": [{"id": "c1", "subject_text": "oficina de Madrid", "predicate_text": "está activa", "object_text": None}],
            },
            {
                "sentence_id": "s2",
                "order_index": 1,
                "text": "Estaba inactiva en 2024.",
                "language": "es",
                "claims": [{"id": "c2", "subject_text": "Estaba inactiva", "predicate_text": "Estaba inactiva", "object_text": "en 2024"}],
            },
        ]
    )
    c2 = r[1]["claims"][0]
    assert c2["subject_text"] == "oficina de Madrid"
    assert c2["predicate_text"] == "estaba inactiva"
    assert c2["context_subject_applied"] is True
    assert c2["context_subject_reason"] == "weak_subject_override"


def test_subject_context_person_anchor_not_compatible_with_state_sentence() -> None:
    r = SubjectContextResolverV1().resolve_claims(
        [
            {
                "sentence_id": "s1",
                "order_index": 0,
                "text": "Sarah Miller is the compliance lead at Zalka 2000.",
                "language": "en",
                "claims": [{"id": "c1", "subject_text": "Sarah Miller", "predicate_text": "is", "object_text": "compliance lead"}],
            },
            {
                "sentence_id": "s2",
                "order_index": 1,
                "text": "Was inactive before March 2025.",
                "language": "en",
                "claims": [{"id": "c2", "subject_text": "Was inactive", "predicate_text": "was inactive", "object_text": "before March 2025"}],
            },
        ]
    )
    c2 = r[1]["claims"][0]
    assert c2["context_subject_applied"] is False
    assert c2["context_subject_reason"] == "incompatible_subject_context:person"


def test_subject_context_trigger_words_are_weak_subject_prefixes() -> None:
    cases = [
        ("hu", "Előtte a belső audit folyamatért", "Kiss Márton"),
        ("hu", "Később a belső audit folyamatért", "Kiss Márton"),
        ("hu", "Akkoriban a belső audit folyamatért", "Kiss Márton"),
        ("en", "Earlier responsible", "Sarah Miller"),
        ("en", "At that time responsible", "Sarah Miller"),
        ("es", "Antes fue", "Carlos García"),
        ("es", "En ese momento fue", "Carlos García"),
    ]
    for language, weak_subject, anchor_subject in cases:
        r = SubjectContextResolverV1().resolve_claims(
            [
                {
                    "sentence_id": "s1",
                    "order_index": 0,
                    "text": f"{anchor_subject} is the compliance lead.",
                    "language": language,
                    "claims": [
                        {"id": "c1", "subject_text": anchor_subject, "predicate_text": "is", "object_text": "compliance lead"}
                    ],
                },
                {
                    "sentence_id": "s2",
                    "order_index": 1,
                    "text": f"{weak_subject} felelt.",
                    "language": language,
                    "claims": [
                        {
                            "id": "c2",
                            "subject_text": weak_subject,
                            "predicate_text": "felelt" if language == "hu" else "responsible",
                            "object_text": "internal audit process",
                        }
                    ],
                },
            ]
        )

        c2 = r[1]["claims"][0]
        assert c2["subject_text"] == anchor_subject
        assert c2["context_subject_applied"] is True
        assert c2["context_subject_reason"] == "weak_subject_override"
