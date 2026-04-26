from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Protocol, Sequence


@dataclass(frozen=True)
class ParsedToken:
    """Abstracted token produced by the NLP pipeline."""

    text: str
    lemma: str
    pos: str
    dep: str
    idx: int
    head_idx: int | None
    char_start: int
    char_end: int
    morph: dict[str, str] = field(default_factory=dict)

    def matches_dep(self, deps: Iterable[str]) -> bool:
        return self.dep in deps

    def matches_pos(self, pos_values: Iterable[str]) -> bool:
        return self.pos in pos_values

    @property
    def normalized(self) -> str:
        return self.text.lower()


@dataclass
class ParsedDoc:
    """Minimal wrapper around tokens that the pipeline returns."""

    text: str
    tokens: list[ParsedToken]
    language_tag: str | None = None

    def span_text(self, start_token: int, end_token: int) -> str:
        if not self.tokens or start_token >= end_token:
            return ""
        start_char = self.tokens[start_token].char_start
        end_char = self.tokens[end_token - 1].char_end
        return self.text[start_char:end_char]

    def token_by_idx(self, idx: int) -> ParsedToken | None:
        if 0 <= idx < len(self.tokens):
            return self.tokens[idx]
        return None


@dataclass(frozen=True)
class TokenSpan:
    start: int
    end: int

    def char_bounds(self, doc: ParsedDoc) -> tuple[int, int]:
        if not doc.tokens or self.start >= self.end:
            return (0, 0)
        start_char = doc.tokens[self.start].char_start
        end_token = doc.tokens[self.end - 1]
        return (start_char, end_token.char_end)

    def text(self, doc: ParsedDoc) -> str:
        start_char, end_char = self.char_bounds(doc)
        if start_char >= end_char:
            return ""
        return doc.text[start_char:end_char]


@dataclass
class ComplementHints:
    attributes: list[ParsedToken] = field(default_factory=list)
    objects: list[ParsedToken] = field(default_factory=list)
    modifiers: list[ParsedToken] = field(default_factory=list)
    extras: list[ParsedToken] = field(default_factory=list)


class NlpPipeline(Protocol):
    def __call__(self, text: str) -> ParsedDoc:
        ...


@dataclass
class ClaimCandidate:
    text_span: str
    subject_hint: str | None
    predicate_hint: str | None
    object_hint: str | None
    start_token: int
    end_token: int
    char_start: int
    char_end: int
    confidence: float
    split_reason: list[str]
