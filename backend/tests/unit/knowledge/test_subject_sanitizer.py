from __future__ import annotations

import pytest

from apps.knowledge.domain.sentence import Sentence
from apps.knowledge.service.claim_extractor_v1 import ClaimExtractorV1
from apps.knowledge.service.claim_sanitizer import sanitize_subject
from apps.knowledge.service.mention_extractor import MentionExtractor


pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


def test_hu_source_phrase_and_suffix_sanitizer_normalizes_subject() -> None:
    assert (
        sanitize_subject("A dokumentum szerint az admin felhasználónak", language="hu")
        == "admin felhasználó"
    )


def test_hu_source_phrase_example_extracts_clean_subject() -> None:
    text = "A dokumentum szerint az admin felhasználónak kötelező kétfaktoros azonosítást használnia."
    sentence = Sentence(text_content=text, metadata={"language": "hu"})
    mentions = MentionExtractor().extract(sentence, language="hu")
    claims = ClaimExtractorV1().extract(sentence, mentions, language="hu")

    assert len(claims) == 1
    assert claims[0].subject_text == "admin felhasználó"
    assert claims[0].predicate_text == "kötelező"
    assert claims[0].object_text == "kétfaktoros azonosítást használnia"
