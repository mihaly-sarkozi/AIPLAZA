from __future__ import annotations

from dataclasses import dataclass

from apps.knowledge.service.language_rules import fold_text, resolve_language


NOISE_SENTENCE_FILTER_VERSION = "noise_sentence_filter_v1"


_NOISE_PHRASES: dict[str, tuple[str, ...]] = {
    "hu": (
        "ez csak zaj",
        "nem kell belőle fontos claim",
        "random tesztmondat",
        "nem kapcsolódik a rendszerhez",
        "csak teszt",
    ),
    "en": (
        "random note",
        "noise sentence",
        "not important",
        "ignore this",
    ),
    "es": (
        "solo ruido",
        "no es importante",
    ),
}


@dataclass(frozen=True)
class NoiseSentenceMatch:
    reason: str
    language: str
    phrase: str
    filter_version: str = NOISE_SENTENCE_FILTER_VERSION


class NoiseSentenceFilterV1:
    version = NOISE_SENTENCE_FILTER_VERSION

    def match(self, text: str | None, *, language: str | None = None) -> NoiseSentenceMatch | None:
        normalized = fold_text(" ".join(str(text or "").strip().split()))
        if not normalized:
            return None
        resolved = resolve_language(text=text, language=language)
        languages = [resolved] if resolved in _NOISE_PHRASES else []
        languages.extend(lang for lang in ("hu", "en", "es") if lang not in languages)
        for lang in languages:
            for phrase in _NOISE_PHRASES[lang]:
                folded_phrase = fold_text(phrase)
                if folded_phrase and folded_phrase in normalized:
                    return NoiseSentenceMatch(reason="noise_sentence", language=lang, phrase=phrase)
        return None

    def is_noise(self, text: str | None, *, language: str | None = None) -> bool:
        return self.match(text, language=language) is not None


__all__ = [
    "NOISE_SENTENCE_FILTER_VERSION",
    "NoiseSentenceFilterV1",
    "NoiseSentenceMatch",
]
