from __future__ import annotations

import pytest

from apps.knowledge.domain.claim import Claim
from apps.knowledge.domain.mention import Mention
from apps.knowledge.domain.sentence import Sentence
from apps.knowledge.service.language_rules import resolve_language
from apps.knowledge.service.space_time_extractor_v1 import SpaceTimeExtractorV1


pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


def _extract_frame(*, text: str, claim_type: str, language: str | None = None):
    resolved_language = resolve_language(text=text, language=language)
    sentence = Sentence(text_content=text, metadata={"language": resolved_language})
    claim = Claim(
        sentence_id=sentence.id,
        source_id=sentence.source_id,
        claim_type=claim_type,
        subject_text="subject",
        predicate_text="predicate",
        object_text="object",
        metadata={"language": resolved_language},
    )
    frame = SpaceTimeExtractorV1().extract(claim, sentence, language=resolved_language)

    print(claim.debug_repr())
    print(frame.debug_repr())

    return claim, sentence, frame, resolved_language


def test_space_time_extractor_hu_current() -> None:
    _claim, _sentence, frame, language = _extract_frame(
        text="A rendszer jelenleg aktív.",
        claim_type="state",
        language="hu",
    )

    assert language == "hu"
    assert frame.time_mode == "current"
    assert frame.time_value == "jelenleg"
    assert frame.overall_confidence >= 0.5


def test_space_time_extractor_en_event() -> None:
    _claim, _sentence, frame, language = _extract_frame(
        text="The account was created in March 2025.",
        claim_type="event",
        language="en",
    )

    assert language == "en"
    assert frame.time_mode in {"bounded", "event"}
    if frame.time_value is not None:
        assert "March 2025" in frame.time_value


def test_space_time_extractor_es_rule() -> None:
    _claim, _sentence, frame, language = _extract_frame(
        text="El usuario debe usar autenticación de dos factores.",
        claim_type="rule_procedure",
        language="es",
    )

    assert language == "es"
    assert frame.time_mode == "zero_time"
    assert frame.space_mode == "irrelevant"


def test_space_time_extractor_hu_location() -> None:
    _claim, _sentence, frame, language = _extract_frame(
        text="A Budapesti iroda aktív.",
        claim_type="state",
        language="hu",
    )

    assert language == "hu"
    assert frame.space_mode == "bounded"


def test_space_time_extractor_prefers_subject_location_phrase() -> None:
    sentence = Sentence(text_content="A Budapesti iroda aktív.", metadata={"language": "hu"})
    claim = Claim(
        sentence_id=sentence.id,
        source_id=sentence.source_id,
        claim_type="state",
        subject_text="Budapesti iroda",
        predicate_text="aktív",
        object_text=None,
        metadata={"language": "hu"},
    )

    frame = SpaceTimeExtractorV1().extract(claim, sentence, language="hu")

    assert frame.space_mode == "bounded"
    assert frame.space_value == "Budapesti iroda"
    assert frame.space_precision == "entity_phrase"


def test_space_time_extractor_prefers_location_mention_over_sentence_snippet_hu() -> None:
    sentence = Sentence(text_content="A Budapesti iroda 2026 márciusában aktív.", metadata={"language": "hu"})
    claim = Claim(
        sentence_id=sentence.id,
        source_id=sentence.source_id,
        claim_type="state",
        subject_text="Budapesti iroda 2026 márciusában",
        predicate_text="aktív",
        object_text=None,
        metadata={"language": "hu"},
    )
    mentions = [
        Mention(sentence_id=sentence.id, text_content="Budapesti iroda", normalized_value="budapesti iroda", mention_type="location"),
    ]

    frame = SpaceTimeExtractorV1().extract(claim, sentence, language="hu", mentions=mentions)

    assert frame.space_mode == "bounded"
    assert frame.space_value == "Budapesti iroda"
    assert frame.space_precision == "mention"


def test_space_time_extractor_prefers_location_mention_over_sentence_snippet_en() -> None:
    sentence = Sentence(text_content="The London office in March 2026 is active.", metadata={"language": "en"})
    claim = Claim(
        sentence_id=sentence.id,
        source_id=sentence.source_id,
        claim_type="state",
        subject_text="London office in March 2026",
        predicate_text="is active",
        object_text=None,
        metadata={"language": "en"},
    )
    mentions = [
        Mention(sentence_id=sentence.id, text_content="London office", normalized_value="london office", mention_type="location"),
    ]

    frame = SpaceTimeExtractorV1().extract(claim, sentence, language="en", mentions=mentions)

    assert frame.space_mode == "bounded"
    assert frame.space_value == "London office"
    assert frame.space_precision == "mention"


def test_space_time_extractor_prefers_location_mention_over_sentence_snippet_es() -> None:
    sentence = Sentence(text_content="La oficina de Madrid en marzo de 2026 está activa.", metadata={"language": "es"})
    claim = Claim(
        sentence_id=sentence.id,
        source_id=sentence.source_id,
        claim_type="state",
        subject_text="oficina de Madrid en marzo de 2026",
        predicate_text="está activa",
        object_text=None,
        metadata={"language": "es"},
    )
    mentions = [
        Mention(sentence_id=sentence.id, text_content="oficina de Madrid", normalized_value="oficina de madrid", mention_type="location"),
    ]

    frame = SpaceTimeExtractorV1().extract(claim, sentence, language="es", mentions=mentions)

    assert frame.space_mode == "bounded"
    assert frame.space_value == "oficina de Madrid"
    assert frame.space_precision == "mention"


def test_space_time_extractor_does_not_treat_company_number_as_year_without_marker() -> None:
    sentence = Sentence(
        text_content="Kovács Péter a Zalka 2000 ügyféltámogatási vezetője.",
        metadata={"language": "hu"},
    )
    claim = Claim(
        sentence_id=sentence.id,
        source_id=sentence.source_id,
        claim_type="relation",
        subject_text="Kovács Péter",
        predicate_text="vezetője",
        object_text="Zalka 2000 ügyféltámogatási",
        metadata={"language": "hu"},
    )

    frame = SpaceTimeExtractorV1().extract(claim, sentence, language="hu")

    assert frame.time_mode in {"unknown", "zero_time"}
    assert frame.time_value is None


def test_space_time_extractor_hu_year_suffix_returns_plain_year() -> None:
    sentence = Sentence(text_content="A dokumentum 2025-ben frissült.", metadata={"language": "hu"})
    claim = Claim(
        sentence_id=sentence.id,
        source_id=sentence.source_id,
        claim_type="event",
        subject_text="dokumentum",
        predicate_text="frissült",
        object_text="2025-ben",
        metadata={"language": "hu"},
    )

    frame = SpaceTimeExtractorV1().extract(claim, sentence, language="hu")

    assert frame.time_mode in {"bounded", "event"}
    assert frame.time_value == "2025"


def test_space_time_extractor_event_prefers_explicit_year_over_event_keyword() -> None:
    sentence = Sentence(text_content="The onboarding checklist was updated in 2023.", metadata={"language": "en"})
    claim = Claim(
        sentence_id=sentence.id,
        source_id=sentence.source_id,
        claim_type="event",
        subject_text="onboarding checklist",
        predicate_text="was updated",
        object_text="in 2023",
        metadata={"language": "en"},
    )

    frame = SpaceTimeExtractorV1().extract(claim, sentence, language="en")

    assert frame.time_mode in {"bounded", "event"}
    assert frame.time_value == "2023"


def test_space_time_extractor_uses_time_nearest_predicate_not_later_sentence_year() -> None:
    sentence = Sentence(
        text_content="A Budapesti iroda 2026 márciusában aktív, 2025-ben tesztüzem.",
        metadata={"language": "hu"},
    )
    claim = Claim(
        sentence_id=sentence.id,
        source_id=sentence.source_id,
        claim_type="state",
        subject_text="Budapesti iroda",
        predicate_text="aktív",
        object_text="2026 márciusában",
        metadata={"language": "hu"},
    )

    frame = SpaceTimeExtractorV1().extract(claim, sentence, language="hu")

    assert frame.time_mode in {"bounded", "current"}
    assert frame.time_value == "2026 márciusában"


def test_space_time_extractor_marks_historical_state_as_bounded_with_before_phrase() -> None:
    sentence = Sentence(
        text_content="The London office was inactive before March 2025.",
        metadata={"language": "en"},
    )
    claim = Claim(
        sentence_id=sentence.id,
        source_id=sentence.source_id,
        claim_type="state",
        subject_text="London office",
        predicate_text="was inactive",
        object_text="before March 2025",
        metadata={"language": "en"},
    )

    frame = SpaceTimeExtractorV1().extract(claim, sentence, language="en")

    assert frame.time_mode == "bounded"
    assert frame.time_value == "before March 2025"


def test_space_time_extractor_keeps_historical_but_clause_from_inheriting_current_marker() -> None:
    sentence = Sentence(
        text_content="The London office is currently inactive, but it was active before January 2025.",
        metadata={"language": "en"},
    )
    claim = Claim(
        sentence_id=sentence.id,
        source_id=sentence.source_id,
        claim_type="state",
        subject_text="London office",
        predicate_text="was active",
        object_text="before January 2025",
        metadata={"language": "en"},
    )

    frame = SpaceTimeExtractorV1().extract(claim, sentence, language="en")

    assert frame.time_mode == "bounded"
    assert frame.time_value == "before January 2025"


def test_space_time_extractor_marks_historical_hungarian_relation_with_korabban() -> None:
    sentence = Sentence(
        text_content="Kiss Márton a Zalka 2000 compliance vezetője, korábban a belső audit folyamatért felelt.",
        metadata={"language": "hu"},
    )
    claim = Claim(
        sentence_id=sentence.id,
        source_id=sentence.source_id,
        claim_type="relation",
        subject_text="Kiss Márton",
        predicate_text="felelt",
        object_text="belső audit folyamatért",
        metadata={"language": "hu"},
    )

    frame = SpaceTimeExtractorV1().extract(claim, sentence, language="hu")

    assert frame.time_mode == "bounded"
    assert frame.time_value == "korábban"


def test_space_time_extractor_detects_hungarian_weekday_as_time_value() -> None:
    sentence = Sentence(text_content="A folyamat hétfőn indul.", metadata={"language": "hu"})
    claim = Claim(
        sentence_id=sentence.id,
        source_id=sentence.source_id,
        claim_type="event",
        subject_text="folyamat",
        predicate_text="indul",
        object_text="hétfőn",
        metadata={"language": "hu"},
    )

    frame = SpaceTimeExtractorV1().extract(claim, sentence, language="hu")

    assert frame.time_mode == "bounded"
    assert frame.time_precision == "weekday"
    assert frame.time_value in {"hétfő", "hetfo"}


def test_space_time_extractor_detects_english_weekday_as_time_value() -> None:
    sentence = Sentence(text_content="The review is scheduled on Monday.", metadata={"language": "en"})
    claim = Claim(
        sentence_id=sentence.id,
        source_id=sentence.source_id,
        claim_type="event",
        subject_text="review",
        predicate_text="is scheduled",
        object_text="Monday",
        metadata={"language": "en"},
    )

    frame = SpaceTimeExtractorV1().extract(claim, sentence, language="en")

    assert frame.time_mode == "bounded"
    assert frame.time_precision == "weekday"
    assert frame.time_value == "Monday"


def test_space_time_extractor_detects_spanish_weekday_as_time_value() -> None:
    sentence = Sentence(text_content="La tarea se ejecuta el lunes.", metadata={"language": "es"})
    claim = Claim(
        sentence_id=sentence.id,
        source_id=sentence.source_id,
        claim_type="event",
        subject_text="tarea",
        predicate_text="se ejecuta",
        object_text="lunes",
        metadata={"language": "es"},
    )

    frame = SpaceTimeExtractorV1().extract(claim, sentence, language="es")

    assert frame.time_mode == "bounded"
    assert frame.time_precision == "weekday"
    assert frame.time_value == "lunes"
