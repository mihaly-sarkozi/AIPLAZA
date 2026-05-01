from apps.knowledge.domain.claim import Claim
from apps.knowledge.domain.sentence import Sentence
from apps.knowledge.service.semantic_block_builder_v1 import SemanticBlockBuilderV1


def _sentence(sentence_id: str, order: int, text: str, paragraph_id: str = "p-1") -> Sentence:
    return Sentence(
        id=sentence_id,
        tenant="demo",
        corpus_uuid="kb-1",
        source_id="src-1",
        document_id="doc-1",
        paragraph_id=paragraph_id,
        order_index=order,
        text_content=text,
    )


def _claim(
    claim_id: str,
    sentence_id: str,
    subject: str,
    predicate: str,
    obj: str,
    *,
    space_label: str | None = None,
    time_label: str | None = None,
) -> Claim:
    return Claim(
        id=claim_id,
        tenant="demo",
        corpus_uuid="kb-1",
        source_id="src-1",
        document_id="doc-1",
        sentence_id=sentence_id,
        subject_text=subject,
        predicate_text=predicate,
        object_text=obj,
        claim_group="state",
        claim_type="state",
        time_mode="current",
        time_label=time_label,
        space_mode="bounded" if space_label else "unknown",
        space_label=space_label,
        confidence=0.8,
    )


def test_semantic_block_builder_groups_contiguous_same_subject_claims() -> None:
    sentences = [
        _sentence("s-1", 1, "A számlázás Stripe-ot használ."),
        _sentence("s-2", 2, "A számlázás automatikus emlékeztetőt küld."),
        _sentence("s-3", 3, "A riport modul exportot készít."),
    ]
    claims = [
        _claim("c-1", "s-1", "számlázás", "használ", "Stripe"),
        _claim("c-2", "s-2", "számlázás", "küld", "emlékeztető"),
        _claim("c-3", "s-3", "riport modul", "készít", "export"),
    ]

    blocks = SemanticBlockBuilderV1().build(sentences=sentences, claims=claims)

    assert len(blocks) == 2
    assert blocks[0].sentence_ids == ["s-1", "s-2"]
    assert blocks[0].claim_ids == ["c-1", "c-2"]
    assert "Stripe" in blocks[0].text
    assert blocks[1].sentence_ids == ["s-3"]


def test_semantic_block_builder_uses_header_context_for_unclaimed_sentences() -> None:
    sentences = [
        Sentence(
            id="s-1",
            corpus_uuid="kb-1",
            source_id="src-1",
            document_id="doc-1",
            paragraph_id="p-1",
            order_index=1,
            text_content="Itt lehet beállítani az értesítéseket.",
            metadata={"header_context_text": "Értesítések"},
        ),
        Sentence(
            id="s-2",
            corpus_uuid="kb-1",
            source_id="src-1",
            document_id="doc-1",
            paragraph_id="p-1",
            order_index=2,
            text_content="E-mail és rendszerüzenet is választható.",
            metadata={"header_context_text": "Értesítések"},
        ),
    ]

    blocks = SemanticBlockBuilderV1().build(sentences=sentences, claims=[])

    assert len(blocks) == 1
    assert blocks[0].primary_subject == "Értesítések"
    assert "E-mail" in blocks[0].text


def test_semantic_block_builder_splits_on_space_or_time_change() -> None:
    sentences = [
        _sentence("s-1", 1, "A londoni iroda 2024-ben bezárt."),
        _sentence("s-2", 2, "A londoni iroda 2025-ben újranyitott."),
        _sentence("s-3", 3, "A budapesti iroda jelenleg aktív."),
    ]
    claims = [
        _claim("c-1", "s-1", "londoni iroda", "állapot", "bezárt", space_label="London", time_label="2024"),
        _claim("c-2", "s-2", "londoni iroda", "állapot", "újranyitott", space_label="London", time_label="2025"),
        _claim("c-3", "s-3", "budapesti iroda", "állapot", "aktív", space_label="Budapest", time_label="jelenleg"),
    ]

    blocks = SemanticBlockBuilderV1().build(sentences=sentences, claims=claims)

    assert len(blocks) == 3
    assert blocks[0].primary_subject == "londoni iroda"
    assert blocks[0].primary_space == "London"
    assert blocks[0].primary_time == "2024"
    assert blocks[1].primary_time == "2025"
    assert blocks[2].primary_space == "Budapest"


def test_semantic_block_builder_keeps_same_subject_space_time_together_when_predicate_changes() -> None:
    sentences = [
        _sentence("s-1", 1, "A bejelentkezés és jelszókezelés tartalmaz belépést."),
        _sentence("s-2", 2, "A bejelentkezés és jelszókezelés támogat jelszócserét."),
        _sentence("s-3", 3, "A bejelentkezés és jelszókezelés kezeli az elfelejtett jelszót."),
    ]
    claims = [
        _claim("c-1", "s-1", "Bejelentkezés és jelszókezelés", "tartalmaz", "belépés"),
        _claim("c-2", "s-2", "Bejelentkezés és jelszókezelés", "támogat", "jelszócsere"),
        _claim("c-3", "s-3", "Bejelentkezés és jelszókezelés", "kezeli", "elfelejtett jelszó"),
    ]

    blocks = SemanticBlockBuilderV1().build(sentences=sentences, claims=claims)

    assert len(blocks) == 1
    assert blocks[0].primary_subject == "Bejelentkezés és jelszókezelés"
    assert blocks[0].sentence_ids == ["s-1", "s-2", "s-3"]
    assert blocks[0].metadata["grouping_rule"] == "sentence_context_subject_space_time_v4"
    assert blocks[0].metadata["sentence_contexts"][0]["resolved_subject"] == "Bejelentkezés és jelszókezelés"


def test_semantic_block_builder_does_not_split_same_context_after_eight_sentences() -> None:
    sentences = [
        _sentence(f"s-{index}", index, f"A bejelentkezés és jelszókezelés {index}. pontja.")
        for index in range(1, 11)
    ]
    claims = [
        _claim(
            f"c-{index}",
            f"s-{index}",
            "Bejelentkezés és jelszókezelés",
            "leír",
            f"{index}. pont",
        )
        for index in range(1, 11)
    ]

    blocks = SemanticBlockBuilderV1().build(sentences=sentences, claims=claims)

    assert len(blocks) == 1
    assert blocks[0].sentence_ids == [f"s-{index}" for index in range(1, 11)]


def test_semantic_block_builder_avoids_imperative_sentence_fragment_as_subject() -> None:
    sentences = [
        _sentence("s-1", 1, "Ne felejtsd el a jelszó megadását a bejelentkezéshez."),
        _sentence("s-2", 2, "A bejelentkezés és jelszókezelés támogatja az elfelejtett jelszó kezelését."),
    ]
    claims = [
        _claim("c-1", "s-1", "Ne felejtsd el a jelszó", "megadás", "bejelentkezés"),
        _claim("c-2", "s-1", "Bejelentkezés és jelszókezelés", "támogatja", "jelszó megadása"),
        _claim("c-3", "s-2", "Bejelentkezés és jelszókezelés", "támogatja", "elfelejtett jelszó kezelése"),
    ]

    blocks = SemanticBlockBuilderV1().build(sentences=sentences, claims=claims)

    assert len(blocks) == 1
    assert blocks[0].primary_subject == "Bejelentkezés és jelszókezelés"
    assert "ne felejtsd" not in blocks[0].subject_key
