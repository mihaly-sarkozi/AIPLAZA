from __future__ import annotations

import pytest

from apps.knowledge.domain.sentence import Sentence
from apps.knowledge.service.mention_extractor import MentionExtractor, debug_print


pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


def test_mention_extraction_basic() -> None:
    sentence = Sentence(
        text_content="A login rendszer kétfaktoros azonosítást használ a Budapesti irodában."
    )
    extractor = MentionExtractor()

    mentions = extractor.extract(sentence)

    debug_print(sentence, mentions)

    normalized_mentions = {item.normalized_text for item in mentions}

    assert len(mentions) >= 3
    assert any("login rendszer" in item for item in normalized_mentions)
    assert any("kétfaktoros azonosítást" in item or "kétfaktoros azonosítás" in item for item in normalized_mentions)
    assert any("budapesti irodában" in item or "budapesti iroda" in item for item in normalized_mentions)


def test_mention_extractor_filters_stopword_only_mentions() -> None:
    sentence = Sentence(text_content="The billing module uses Stripe.")

    mentions = MentionExtractor().extract(sentence, language="en")

    surface_texts = {item.surface_text for item in mentions}
    assert "The" not in surface_texts
    assert any(item.surface_text == "billing module" for item in mentions)


def test_mention_extractor_strips_leading_articles_in_spanish() -> None:
    sentence = Sentence(text_content="El sistema de inicio de sesión utiliza autenticación de dos factores.")

    mentions = MentionExtractor().extract(sentence, language="es")

    surface_texts = {item.surface_text for item in mentions}
    assert "El" not in surface_texts
    assert any("sistema de inicio de sesión" == item for item in surface_texts)


def test_mention_extractor_detects_sentence_language() -> None:
    sentence = Sentence(text_content="La oficina de Madrid está actualmente activa.")

    mentions = MentionExtractor().extract(sentence)

    assert mentions
    assert all(item.metadata.get("language") == "es" for item in mentions)


def test_mention_extractor_keeps_company_number_phrase_together() -> None:
    sentence = Sentence(text_content="Kovács Péter a Zalka 2000 ügyféltámogatási vezetője.")

    mentions = MentionExtractor().extract(sentence, language="hu")

    surface_texts = {item.surface_text for item in mentions}
    assert "Zalka 2000" in surface_texts
    assert "2000" not in surface_texts


def test_mention_extractor_prefers_location_phrase_over_shorter_capitalized_subspan() -> None:
    sentence = Sentence(text_content="The London office is active.")

    mentions = MentionExtractor().extract(sentence, language="en")

    surface_texts = {item.surface_text for item in mentions}
    assert "London office" in surface_texts
    assert "London" not in surface_texts
    assert not any(item.mention_type == "person" and item.surface_text in {"The London", "London"} for item in mentions)


def test_mention_extractor_drops_repeated_token_noise_span() -> None:
    sentence = Sentence(text_content="Stripe Stripe should not become a person mention.")

    mentions = MentionExtractor().extract(sentence, language="en")

    assert all(item.surface_text != "Stripe Stripe" for item in mentions)
    assert all(not (item.surface_text == "Stripe Stripe" and item.mention_type == "person") for item in mentions)


def test_mention_extractor_classifies_capitalized_location_keyword_span_as_location() -> None:
    sentence = Sentence(text_content="Madrid Oficina está activa.")

    mentions = MentionExtractor().extract(sentence, language="es")

    madrid_oficina = next((item for item in mentions if item.surface_text == "Madrid Oficina"), None)
    assert madrid_oficina is not None
    assert madrid_oficina.mention_type == "location"
