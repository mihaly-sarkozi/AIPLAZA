from __future__ import annotations

import logging
import os
from pathlib import Path
import re
from typing import Any

try:
    import spacy  # type: ignore[import]
    from spacy.language import Language as SpacyLanguage
    from spacy.tokens import Doc
except ImportError:  # pragma: no cover - optional dependency
    spacy = None
    SpacyLanguage = Any  # type: ignore[misc, assignment]
    Doc = Any  # type: ignore[misc, assignment]

try:
    import stanza  # type: ignore[import]
except ImportError:  # pragma: no cover - optional dependency
    stanza = None

try:
    import huspacy  # type: ignore[import]
except ImportError:  # pragma: no cover - optional dependency
    huspacy = None

from .types import NlpPipeline, ParsedDoc, ParsedToken

LOGGER = logging.getLogger(__name__)

STANZA_MODEL_DIR = Path(os.environ.get("STANZA_MODEL_DIR", ".stanza_models")).resolve()


def _ensure_stanza_dir() -> Path:
    STANZA_MODEL_DIR.mkdir(parents=True, exist_ok=True)
    return STANZA_MODEL_DIR


def _normalize_morph(value: Any) -> dict[str, str]:
    if not value:
        return {}
    if hasattr(value, "to_dict"):
        value = value.to_dict()
    if isinstance(value, dict):
        normalized: dict[str, str] = {}
        for key, item in value.items():
            if item is None:
                continue
            if isinstance(item, (list, tuple, set)):
                parts = [str(part) for part in item if part not in (None, "")]
                if parts:
                    normalized[str(key)] = "|".join(parts)
                continue
            if item != "":
                normalized[str(key)] = str(item)
        return normalized
    if isinstance(value, str):
        normalized: dict[str, str] = {}
        for part in value.split("|"):
            if "=" not in part:
                continue
            key, item = part.split("=", 1)
            key = key.strip()
            item = item.strip()
            if key and item:
                normalized[key] = item
        return normalized
    return {}


def _spacy_doc_to_parsed(doc: Doc, *, language_tag: str | None = None) -> ParsedDoc:
    tokens: list[ParsedToken] = []
    for token in doc:
        tokens.append(
            ParsedToken(
                text=token.text,
                lemma=token.lemma_,
                pos=token.pos_,
                dep=token.dep_,
                idx=token.i,
                head_idx=token.head.i if token.head is not None else None,
                char_start=token.idx,
                char_end=token.idx + len(token.text),
                morph=_normalize_morph(token.morph),
            )
        )
    return ParsedDoc(text=doc.text, tokens=tokens, language_tag=language_tag)


def _stanza_doc_to_parsed(doc: stanza.Document, *, language_tag: str | None = None) -> ParsedDoc:
    tokens: list[ParsedToken] = []
    sentence_offset = 0
    for sentence in doc.sentences:
        for token in sentence.tokens:
            word = token.words[0]
            idx = sentence_offset + (word.id - 1)
            head_idx = sentence_offset + (word.head - 1) if word.head > 0 else None
            tokens.append(
                ParsedToken(
                    text=word.text,
                    lemma=word.lemma or word.text,
                    pos=word.upos,
                    dep=word.deprel,
                    idx=idx,
                    head_idx=head_idx,
                    char_start=token.start_char,
                    char_end=token.end_char,
                    morph=_normalize_morph(word.feats),
                )
            )
        sentence_offset += len(sentence.tokens)
    return ParsedDoc(text=doc.text, tokens=tokens, language_tag=language_tag)


class SpaCyPipeline(NlpPipeline):
    def __init__(self, nlp: SpacyLanguage, *, language_tag: str | None = None) -> None:
        self._nlp = nlp
        self._language_tag = language_tag

    def __call__(self, text: str) -> ParsedDoc:
        return _spacy_doc_to_parsed(self._nlp(text), language_tag=self._language_tag)


class HuSpaCyPipeline(SpaCyPipeline):
    def __init__(self, *, model_name: str | None = None) -> None:
        if huspacy is None:
            raise ImportError("huspacy is not installed")
        nlp = huspacy.load(model_name) if model_name else huspacy.load()
        super().__init__(nlp=nlp, language_tag="hu")


class StanzaPipeline(NlpPipeline):
    def __init__(self, lang: str, *, processors: str = "tokenize,pos,lemma,depparse") -> None:
        if stanza is None:
            raise ImportError("stanza is not installed")
        stanza_dir = _ensure_stanza_dir()
        self._lang = lang
        self._nlp = stanza.Pipeline(lang=lang, processors=processors, dir=str(stanza_dir), use_gpu=False, verbose=False)

    def __call__(self, text: str) -> ParsedDoc:
        doc = self._nlp(text)
        return _stanza_doc_to_parsed(doc, language_tag=self._lang)


class RegexNlpPipeline(NlpPipeline):
    """Lightweight fallback pipeline that emits tokens based on word boundaries."""
    def __init__(self, *, language_tag: str | None = None) -> None:
        self.language_tag = language_tag

    def __call__(self, text: str) -> ParsedDoc:
        tokens: list[ParsedToken] = []
        for idx, match in enumerate(re.finditer(r"\b\w+\b", text, flags=re.UNICODE)):
            word = match.group(0)
            tokens.append(
                ParsedToken(
                    text=word,
                    lemma=word.lower(),
                    pos=self._guess_pos(word),
                    dep="ROOT" if idx == 0 else "dep",
                    idx=idx,
                    head_idx=0 if idx != 0 else None,
                    char_start=match.start(),
                    char_end=match.end(),
                )
            )
        return ParsedDoc(text=text, tokens=tokens, language_tag=self.language_tag)

    @staticmethod
    def _guess_pos(word: str) -> str:
        lowered = word.lower()
        if lowered.endswith(("ni", "ik", "ok", "ünk", "nek")):
            return "VERB"
        if lowered.endswith(("ban", "ben", "ra", "re", "hoz", "hez")):
            return "NOUN"
        return "NOUN"
