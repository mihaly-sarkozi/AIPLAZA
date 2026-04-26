from __future__ import annotations

from uuid import uuid4

import pytest

from apps.knowledge.domain.sentence import Sentence
from apps.knowledge.service.claim_extractor_v1 import ClaimExtractorV1
from apps.knowledge.service.mention_extractor import MentionExtractor
from apps.knowledge.service.subject_context_resolver_v1 import SubjectContextResolverV1


pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


def _extract_and_resolve(texts: list[str], *, language: str) -> list[tuple[str, str, str | None]]:
    source_id = str(uuid4())
    document_id = str(uuid4())
    rows = []
    for index, text in enumerate(texts):
        sentence = Sentence(
            source_id=source_id,
            document_id=document_id,
            order_index=index,
            text_content=text,
            metadata={"language": language},
        )
        mentions = MentionExtractor().extract(sentence, language=language)
        claims = ClaimExtractorV1().extract(sentence, mentions, language=language)
        rows.append(
            {
                "sentence_id": str(sentence.id),
                "order_index": index,
                "text": text,
                "language": language,
                "mentions": mentions,
                "claims": claims,
            }
        )

    resolved = SubjectContextResolverV1().resolve_claims(rows)
    return [
        (claim.subject_text, claim.predicate_text, claim.object_text)
        for row in resolved
        for claim in row["claims"]
    ]


def test_hu_context_carryover_resolves_implicit_subject() -> None:
    assert _extract_and_resolve(
        [
            "Nagy Eszter a Zalka 2000 adatvédelmi felelőse.",
            "Korábban a belső incidenskezelési folyamatért felelt.",
        ],
        language="hu",
    ) == [
        ("Nagy Eszter", "adatvédelmi felelőse", "Zalka 2000"),
        ("Nagy Eszter", "felelt", "belső incidenskezelési folyamatért"),
    ]


def test_en_context_carryover_resolves_implicit_subject() -> None:
    assert _extract_and_resolve(
        [
            "Sarah Miller is the compliance lead at Zalka 2000.",
            "Previously responsible for the internal audit process.",
        ],
        language="en",
    ) == [
        ("Sarah Miller", "is the compliance lead at", "Zalka 2000"),
        ("Sarah Miller", "responsible", "for the internal audit process"),
    ]


def test_es_context_carryover_resolves_implicit_subject() -> None:
    assert _extract_and_resolve(
        [
            "Carlos García es el responsable de compliance en Zalka 2000.",
            "Anteriormente fue responsable del proceso de auditoría interna.",
        ],
        language="es",
    ) == [
        ("Carlos García", "es", "responsable de compliance en Zalka 2000"),
        ("Carlos García", "fue", "responsable del proceso de auditoría interna"),
    ]
