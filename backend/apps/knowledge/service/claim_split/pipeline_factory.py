from __future__ import annotations

from .language_router import LanguageRouter
from .pipeline import HuSpaCyPipeline, RegexNlpPipeline, SpaCyPipeline, StanzaPipeline
from .splitter import ClaimFineSplitter
from .types import NlpPipeline
import logging

try:
    import spacy  # type: ignore[import]
except ImportError:  # pragma: no cover - optional dependency
    spacy = None

try:
    import huspacy  # type: ignore[import]
except ImportError:
    huspacy = None

LOGGER = logging.getLogger(__name__)


def _build_stanza_pipeline(lang: str) -> NlpPipeline:
    try:
        return StanzaPipeline(lang=lang)
    except Exception as exc:
        LOGGER.warning("Stanza pipeline %s failed: %s; falling back to regex", lang, exc)
        return RegexNlpPipeline(language_tag=lang)


def _build_spacy_pipeline(model_name: str, lang: str) -> NlpPipeline:
    if spacy is None:
        LOGGER.warning("spaCy is not installed; falling back to Stanza")
        return _build_stanza_pipeline(lang)
    try:
        return SpaCyPipeline(spacy.load(model_name), language_tag=lang)
    except Exception as exc:
        LOGGER.warning("spaCy model %s not available: %s; falling back to Stanza", model_name, exc)
        return _build_stanza_pipeline(lang)


def _build_huspacy_pipeline() -> NlpPipeline:
    if huspacy is None:
        LOGGER.warning("huspacy is not installed; falling back to Stanza")
        return _build_stanza_pipeline("hu")
    try:
        return HuSpaCyPipeline()
    except Exception as exc:
        LOGGER.warning("HuSpaCy initialization failed: %s; falling back to Stanza", exc)
        return _build_stanza_pipeline("hu")


def build_default_claim_fine_splitter() -> ClaimFineSplitter:
    language_pipelines = {
        "huspacy": _build_huspacy_pipeline(),
        "spacy_en": _build_spacy_pipeline("en_core_web_sm", "en"),
        "spacy_es": _build_spacy_pipeline("es_core_news_sm", "es"),
    }
    router = LanguageRouter(pipelines=language_pipelines, fallback=_build_stanza_pipeline("en"))
    return ClaimFineSplitter(language_router=router)
