from __future__ import annotations

from uuid import uuid4

import pytest

from apps.knowledge.domain.claim import Claim, ClaimStatus, ClaimType
from apps.knowledge.domain.local_entity_cluster import LocalEntityType
from apps.knowledge.domain.sentence import Sentence
from apps.knowledge.domain.mention import Mention, MentionType
from apps.knowledge.service.entity_key_normalization import normalize_entity_key
from apps.knowledge.service.claim_extractor_v1 import ClaimExtractorV1
from apps.knowledge.service.local_resolver_v1 import LocalResolverV1, infer_entity_type
from apps.knowledge.service.mention_extractor import MentionExtractor
from apps.knowledge.service.subject_context_resolver_v1 import SubjectContextResolverV1

pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


def test_normalize_entity_key_used_for_clustering() -> None:
    assert normalize_entity_key("  ACME   Corp. ") == "acme corp"


def test_clusters_merge_same_subject_text_and_key() -> None:
    mid = str(uuid4())
    sid1 = str(uuid4())
    sid2 = str(uuid4())
    run_id = uuid4()
    source_id = uuid4()
    mention = Mention(
        id=mid,
        mention_type=MentionType.COMPANY,
        text_content="ACME Ltd",
        normalized_value="acme ltd",
        sentence_id=sid1,
    )
    c1 = Claim(
        subject_mention_id=mid,
        subject_text="ACME Ltd",
        predicate_text="has",
        object_text="policy",
        sentence_id=sid1,
        confidence=0.8,
    )
    c2 = Claim(
        subject_mention_id=mid,
        subject_text="ACME Ltd",
        predicate_text="owns",
        object_text="subsidiary",
        sentence_id=sid2,
        confidence=0.9,
    )
    resolver = LocalResolverV1()
    sentences = [
        Sentence(id=sid1, order_index=0),
        Sentence(id=sid2, order_index=1),
    ]
    clusters, trace = resolver.resolve_with_trace(run_id, source_id, sentences, [mention], [c1, c2])
    plain = resolver.resolve(run_id, source_id, sentences, [mention], [c1, c2])
    assert len(plain) == len(clusters) == 1
    a, b = plain[0], clusters[0]
    assert a.claim_ids == b.claim_ids
    assert a.normalized_key == b.normalized_key
    assert a.entity_type == b.entity_type
    assert a.canonical_name == b.canonical_name
    assert a.coherence_score == b.coherence_score
    assert a.explanation == b.explanation

    assert len(clusters) == 1
    assert len(clusters[0].claim_ids) == 2
    assert clusters[0].entity_type == LocalEntityType.COMPANY.value
    assert clusters[0].explanation.get("grouping_rule") == "normalized_subject_key"
    assert clusters[0].explanation.get("entity_type_source") == "mention_match"
    assert clusters[0].explanation.get("claim_count") == 2
    assert isinstance(clusters[0].explanation.get("coherence_factors"), list)
    assert clusters[0].run_id == run_id
    assert clusters[0].source_id == source_id
    assert len(trace["decisions"]) == 2
    assert all(row["rule"] == "subject_text_candidate" for row in trace["decisions"])
    assert trace["decisions"][0]["candidate"]["canonical_name"] == "ACME Ltd"
    assert trace["resolver_version"] == "local_resolver_v1"


def test_fallback_subject_text_groups_identical_normalized() -> None:
    sid = str(uuid4())
    c1 = Claim(subject_text="Widget", predicate_text="is", object_text="ready", sentence_id=sid, confidence=0.7)
    c2 = Claim(subject_text="widget", predicate_text="was", object_text="tested", sentence_id=sid, confidence=0.6)
    sentences = [Sentence(id=sid, order_index=0)]
    clusters, trace = LocalResolverV1().resolve_with_trace(None, None, sentences, [], [c1, c2])
    assert len(clusters) == 1
    assert clusters[0].entity_type == LocalEntityType.UNKNOWN.value
    assert trace["decisions"][0]["rule"] == "subject_text_candidate"
    assert trace["decisions"][0]["candidate"].get("entity_type_source") == "fallback"


def test_infer_entity_type_object_mention_overlap() -> None:
    mid = str(uuid4())
    sid = str(uuid4())
    m = Mention(
        id=mid,
        mention_type=MentionType.OBJECT,
        text_content="widget",
        normalized_value="widget",
        sentence_id=sid,
    )
    c = Claim(subject_mention_id=mid, subject_text="widget", sentence_id=sid)
    assert infer_entity_type(c, [m]) == LocalEntityType.OBJECT.value


@pytest.mark.parametrize(
    ("subject", "expected"),
    [
        ("London office", LocalEntityType.LOCATION.value),
        ("Budapesti iroda", LocalEntityType.LOCATION.value),
        ("oficina de Madrid", LocalEntityType.LOCATION.value),
        ("Kiss Márton", LocalEntityType.PERSON.value),
        ("Sarah Miller", LocalEntityType.PERSON.value),
        ("Carlos García", LocalEntityType.PERSON.value),
        ("Zalka 2000", LocalEntityType.COMPANY.value),
        ("Login rendszer", LocalEntityType.SYSTEM.value),
        ("Billing module", LocalEntityType.MODULE.value),
        ("The user", LocalEntityType.USER.value),
        ("Main account", LocalEntityType.ACCOUNT.value),
        ("Privacy policy", LocalEntityType.POLICY.value),
        ("This document", LocalEntityType.DOCUMENT.value),
        ("Insurance claim", LocalEntityType.OBJECT.value),
        ("random widget", LocalEntityType.UNKNOWN.value),
    ],
)
def test_infer_entity_type_keyword_and_patterns(subject: str, expected: str) -> None:
    assert infer_entity_type(Claim(subject_text=subject), []) == expected


def test_infer_entity_type_mention_overlap_beats_keyword() -> None:
    sid = str(uuid4())
    m = Mention(
        id=str(uuid4()),
        mention_type=MentionType.PERSON,
        text_content="London",
        normalized_value="london",
        sentence_id=sid,
    )
    c = Claim(subject_text="London office", sentence_id=sid, subject_mention_id=str(m.id))
    assert infer_entity_type(c, [m]) == LocalEntityType.PERSON.value


def test_v1_merge_unknown_with_concrete_same_normalized_key() -> None:
    sid = str(uuid4())
    mid = str(uuid4())
    mention = Mention(
        id=mid,
        mention_type=MentionType.COMPANY,
        text_content="Acme Corp",
        normalized_value="acme corp",
        sentence_id=sid,
    )
    c_unknown = Claim(subject_text="Acme Corp", sentence_id=sid, confidence=0.5)
    c_company = Claim(
        subject_mention_id=mid,
        subject_text="Acme Corp",
        sentence_id=sid,
        confidence=0.9,
    )
    sentences = [Sentence(id=sid, order_index=0)]
    clusters, trace = LocalResolverV1().resolve_with_trace(None, None, sentences, [mention], [c_unknown, c_company])
    assert len(clusters) == 1
    assert clusters[0].entity_type == LocalEntityType.COMPANY.value
    assert len(clusters[0].claim_ids) == 2
    assert clusters[0].normalized_key == normalize_entity_key("Acme Corp")
    assert any(r["resolution"] == "merged_unknown_into_concrete" for r in trace["entity_type_resolutions"])


def test_v1_conflict_split_concrete_types_same_normalized_key() -> None:
    sid = str(uuid4())
    mp = str(uuid4())
    mc = str(uuid4())
    m_person = Mention(
        id=mp,
        mention_type=MentionType.PERSON,
        text_content="Jan Kowalski",
        normalized_value="jan kowalski",
        sentence_id=sid,
    )
    m_company = Mention(
        id=mc,
        mention_type=MentionType.COMPANY,
        text_content="Jan Kowalski",
        normalized_value="jan kowalski",
        sentence_id=sid,
    )
    c_person = Claim(subject_mention_id=mp, subject_text="Jan Kowalski", sentence_id=sid)
    c_company = Claim(subject_mention_id=mc, subject_text="Jan Kowalski", sentence_id=sid)
    sentences = [Sentence(id=sid, order_index=0)]
    clusters, trace = LocalResolverV1().resolve_with_trace(
        None, None, sentences, [m_person, m_company], [c_person, c_company]
    )
    assert len(clusters) == 2
    assert {c.entity_type for c in clusters} == {LocalEntityType.PERSON.value, LocalEntityType.COMPANY.value}
    assert trace["entity_type_resolutions"][0]["resolution"] == "conflict_split"


def test_cluster_canonical_prefers_title_case_when_frequency_tied() -> None:
    sid = str(uuid4())
    sentences = [Sentence(id=sid, order_index=0)]
    c1 = Claim(subject_text="london office", sentence_id=sid, confidence=0.99)
    c2 = Claim(subject_text="London office", sentence_id=sid, confidence=0.01)
    clusters = LocalResolverV1().resolve(None, None, sentences, [], [c1, c2])
    assert len(clusters) == 1
    assert clusters[0].canonical_name == "London office"
    assert set(clusters[0].surface_forms) == {"london office", "London office"}


def test_cluster_canonical_kiss_marton_unified() -> None:
    sid = str(uuid4())
    sentences = [Sentence(id=sid, order_index=0)]
    c1 = Claim(subject_text="Kiss Márton", sentence_id=sid, confidence=0.6)
    c2 = Claim(subject_text="Kiss Márton", sentence_id=sid, confidence=0.7)
    clusters = LocalResolverV1().resolve(None, None, sentences, [], [c1, c2])
    assert clusters[0].canonical_name == "Kiss Márton"
    assert clusters[0].surface_forms == ["Kiss Márton"]


def test_surface_forms_include_matching_mention_surface() -> None:
    sid = str(uuid4())
    mid = str(uuid4())
    m = Mention(
        id=mid,
        mention_type=MentionType.LOCATION,
        text_content="London HQ",
        normalized_value="london hq",
        sentence_id=sid,
    )
    c = Claim(
        subject_mention_id=mid,
        subject_text="London HQ branch",
        sentence_id=sid,
        confidence=0.5,
    )
    clusters = LocalResolverV1().resolve(None, None, [Sentence(id=sid, order_index=0)], [m], [c])
    assert set(clusters[0].surface_forms) >= {"London HQ", "London HQ branch"}


def test_login_rendszer_and_login_system_remain_separate_clusters() -> None:
    sid = str(uuid4())
    sentences = [Sentence(id=sid, order_index=0)]
    c_hu = Claim(subject_text="login rendszer", sentence_id=sid)
    c_en = Claim(subject_text="login system", sentence_id=sid)
    clusters = LocalResolverV1().resolve(None, None, sentences, [], [c_hu, c_en])
    assert len(clusters) == 2
    keys = {c.normalized_key for c in clusters}
    assert len(keys) == 2


def test_carryover_sentence_trigger_phrase_does_not_become_entity_name() -> None:
    texts = [
        "Nagy Eszter a Zalka 2000 adatvédelmi felelőse.",
        "Korábban a belső incidenskezelési folyamatért felelt.",
    ]
    run_id = str(uuid4())
    source_id = str(uuid4())
    document_id = str(uuid4())
    sentences: list[Sentence] = []
    mentions: list[Mention] = []
    rows = []

    for index, text in enumerate(texts):
        sentence = Sentence(
            source_id=source_id,
            document_id=document_id,
            order_index=index,
            text_content=text,
            metadata={"language": "hu"},
        )
        sentence_mentions = MentionExtractor().extract(sentence, language="hu")
        sentence_claims = ClaimExtractorV1().extract(sentence, sentence_mentions, language="hu")
        sentences.append(sentence)
        mentions.extend(sentence_mentions)
        rows.append(
            {
                "sentence_id": str(sentence.id),
                "order_index": index,
                "text": text,
                "language": "hu",
                "mentions": sentence_mentions,
                "claims": sentence_claims,
            }
        )

    resolved_claims = [claim for row in SubjectContextResolverV1().resolve_claims(rows) for claim in row["claims"]]
    clusters = LocalResolverV1().resolve(run_id, source_id, sentences, mentions, resolved_claims, language="hu")

    assert [(claim.subject_text, claim.predicate_text, claim.object_text) for claim in resolved_claims] == [
        ("Nagy Eszter", "adatvédelmi felelőse", "Zalka 2000"),
        ("Nagy Eszter", "felelt", "belső incidenskezelési folyamatért"),
    ]
    assert len(clusters) == 1
    assert clusters[0].canonical_name == "Nagy Eszter"
    assert clusters[0].entity_type == LocalEntityType.PERSON.value
    assert len(clusters[0].claim_ids) == 2


def test_coherence_penalty_multiple_claim_types_and_unknown_entity() -> None:
    sid = str(uuid4())
    sentences = [Sentence(id=sid, order_index=0)]
    c1 = Claim(
        subject_text="Acme",
        claim_type=ClaimType.STATE.value,
        sentence_id=sid,
        confidence=0.9,
    )
    c2 = Claim(
        subject_text="Acme",
        claim_type=ClaimType.OPINION.value,
        sentence_id=sid,
        confidence=0.9,
    )
    clusters = LocalResolverV1().resolve(None, None, sentences, [], [c1, c2])
    assert len(clusters) == 1
    assert clusters[0].coherence_score == pytest.approx(0.8)


def test_coherence_penalty_claim_status_conflict_same_time() -> None:
    sid = str(uuid4())
    sentences = [Sentence(id=sid, order_index=0)]
    c1 = Claim(
        subject_text="Zeta rule",
        claim_group="grp",
        time_mode="current",
        time_label="Q1",
        claim_status=ClaimStatus.ACTIVE.value,
        claim_type=ClaimType.STATE.value,
        sentence_id=sid,
        confidence=0.9,
    )
    c2 = Claim(
        subject_text="Zeta rule",
        claim_group="grp",
        time_mode="current",
        time_label="Q1",
        claim_status=ClaimStatus.BANNED.value,
        claim_type=ClaimType.STATE.value,
        sentence_id=sid,
        confidence=0.9,
    )
    clusters = LocalResolverV1().resolve(None, None, sentences, [], [c1, c2])
    assert clusters[0].coherence_score == pytest.approx(0.6)


def test_coherence_penalty_low_confidence() -> None:
    sid = str(uuid4())
    c = Claim(subject_text="X", sentence_id=sid, confidence=0.5)
    clusters = LocalResolverV1().resolve(None, None, [Sentence(id=sid)], [], [c])
    assert clusters[0].coherence_score == pytest.approx(0.8)


def test_cluster_evidence_refs_and_mention_ids_include_object_mention() -> None:
    sid = str(uuid4())
    smid = str(uuid4())
    omid = str(uuid4())
    c = Claim(
        id=str(uuid4()),
        subject_text="Acme",
        predicate_text="owns",
        object_text="Beta",
        claim_type="relation",
        time_mode="current",
        time_label="Q1",
        space_mode="region",
        space_label="EU",
        sentence_id=sid,
        subject_mention_id=smid,
        object_mention_id=omid,
    )
    clusters = LocalResolverV1().resolve(None, None, [Sentence(id=sid, order_index=0)], [], [c])
    assert len(clusters) == 1
    ref = clusters[0].evidence_refs[0]
    assert ref == {
        "sentence_id": sid,
        "claim_id": c.claim_id,
        "claim_type": "relation",
        "predicate": "owns",
        "object_text": "Beta",
        "time_mode": "current",
        "time_value": "Q1",
        "space_mode": "region",
        "space_value": "EU",
    }
    mid_strs = {str(u) for u in clusters[0].mention_ids}
    assert smid in mid_strs and omid in mid_strs


def test_debug_repr_local_entity_cluster() -> None:
    cid = uuid4()
    sid = str(uuid4())
    sentences = [Sentence(id=sid, order_index=0)]
    clusters = LocalResolverV1().resolve(
        None,
        None,
        sentences,
        [],
        [
            Claim(
                id=str(cid),
                subject_text="X",
                predicate_text="p",
                object_text=None,
                sentence_id=sid,
                confidence=0.5,
            )
        ],
    )
    text = clusters[0].debug_repr()
    assert "[LOCAL ENTITY]" in text
    assert "claims=1" in text
    assert "mentions=0" in text
    assert "coherence=" in text
    assert "key=" in text


@pytest.mark.parametrize(
    ("subject", "pred1", "obj1", "pred2", "obj2"),
    [
        ("keresési modul", "használ", "Qdrant indexet", "használ", "OpenAI embeddinget"),
        ("search module", "uses", "Qdrant index", "uses", "OpenAI embeddings"),
        ("módulo de búsqueda", "utiliza", "índice Qdrant", "utiliza", "embeddings de OpenAI"),
    ],
)
def test_search_module_like_subject_two_sentences_merge_one_cluster_two_claims(
    subject: str, pred1: str, obj1: str, pred2: str, obj2: str
) -> None:
    """Trace / local resolver: ugyanahhoz a modul-entitáshoz két claim egy klaszterben (HU/EN/ES)."""
    sid1 = str(uuid4())
    sid2 = str(uuid4())
    run_id = uuid4()
    source_id = uuid4()
    c1 = Claim(
        subject_text=subject,
        predicate_text=pred1,
        object_text=obj1,
        sentence_id=sid1,
        confidence=0.85,
        claim_type="relation",
    )
    c2 = Claim(
        subject_text=subject,
        predicate_text=pred2,
        object_text=obj2,
        sentence_id=sid2,
        confidence=0.85,
        claim_type="relation",
    )
    sentences = [Sentence(id=sid1, order_index=0), Sentence(id=sid2, order_index=1)]
    clusters = LocalResolverV1().resolve(run_id, source_id, sentences, [], [c1, c2])
    assert len(clusters) == 1
    assert len(clusters[0].claim_ids) == 2
    assert clusters[0].entity_type == LocalEntityType.MODULE.value
