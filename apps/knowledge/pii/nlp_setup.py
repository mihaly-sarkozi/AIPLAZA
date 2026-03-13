# apps/knowledge/pii/nlp_setup.py
"""
Presidio NLP engine és analyzer példányok: angol + spanyol = spaCy, magyar = Stanza.
Lazy init: csak az első használatkor töltődnek a modellek.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from presidio_analyzer import AnalyzerEngine

# Lazy singletons
_analyzer_en_es: "AnalyzerEngine | None" = None
_analyzer_hu: "AnalyzerEngine | None" = None
_analyzer_en_es_error: Exception | None = None
_analyzer_hu_error: Exception | None = None


def get_analyzer_en_es() -> "AnalyzerEngine | None":
    """Presidio analyzer angol és spanyol szövegre: spaCy NER + egyéni regex recognizerek."""
    global _analyzer_en_es, _analyzer_en_es_error
    if _analyzer_en_es_error is not None:
        return None
    if _analyzer_en_es is not None:
        return _analyzer_en_es
    try:
        from presidio_analyzer import AnalyzerEngine, RecognizerRegistry
        from presidio_analyzer.nlp_engine import NlpEngineProvider
        from apps.knowledge.pii.recognizers import get_custom_recognizers

        configuration = {
            "nlp_engine_name": "spacy",
            "models": [
                {"lang_code": "en", "model_name": "en_core_web_sm"},
                {"lang_code": "es", "model_name": "es_core_news_sm"},
            ],
        }
        provider = NlpEngineProvider(nlp_configuration=configuration)
        nlp_engine = provider.create_engine()

        # Angol + spanyol: Spacy NER (en, es) + egyéni regex
        registry = RecognizerRegistry()
        try:
            from presidio_analyzer.predefined_recognizers import SpacyRecognizer
            registry.add_recognizer(SpacyRecognizer(supported_language="en"))
            registry.add_recognizer(SpacyRecognizer(supported_language="es"))
        except Exception:
            pass
        for lang in ("en", "es"):
            for rec in get_custom_recognizers(lang):
                registry.add_recognizer(rec)

        # supported_languages ne legyen megadva: a registry-ből veszi (en + es)
        _analyzer_en_es = AnalyzerEngine(
            nlp_engine=nlp_engine,
            registry=registry,
        )
        return _analyzer_en_es
    except Exception as e:
        _analyzer_en_es_error = e
        return None


def get_analyzer_hu() -> "AnalyzerEngine | None":
    """Presidio analyzer magyar szövegre: Stanza NER + egyéni regex recognizerek."""
    global _analyzer_hu, _analyzer_hu_error
    if _analyzer_hu_error is not None:
        return None
    if _analyzer_hu is not None:
        return _analyzer_hu
    try:
        from presidio_analyzer import AnalyzerEngine, RecognizerRegistry
        from presidio_analyzer.nlp_engine import NlpEngineProvider
        from apps.knowledge.pii.recognizers import get_custom_recognizers

        configuration = {
            "nlp_engine_name": "stanza",
            "models": [
                {"lang_code": "hu", "model_name": "hu"},
            ],
        }
        provider = NlpEngineProvider(nlp_configuration=configuration)
        nlp_engine = provider.create_engine()

        # Magyarhoz csak Stanza NER + egyéni regex (SpacyRecognizer ne legyen)
        registry = RecognizerRegistry()
        try:
            from presidio_analyzer.predefined_recognizers import StanzaRecognizer
            registry.add_recognizer(StanzaRecognizer())
        except Exception:
            pass
        for rec in get_custom_recognizers("hu"):
            registry.add_recognizer(rec)

        _analyzer_hu = AnalyzerEngine(
            nlp_engine=nlp_engine,
            registry=registry,
        )
        return _analyzer_hu
    except Exception as e:
        _analyzer_hu_error = e
        return None


def get_analyzer_for_language(lang: str) -> "AnalyzerEngine | None":
    """Nyelv alapján a megfelelő analyzer: hu → Stanza, en/es → spaCy."""
    if lang == "hu":
        return get_analyzer_hu()
    if lang in ("en", "es"):
        return get_analyzer_en_es()
    return get_analyzer_en_es()
