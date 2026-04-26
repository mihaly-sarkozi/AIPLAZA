from __future__ import annotations

from dataclasses import dataclass

from .types import NlpPipeline


@dataclass
class LanguageRouter:
    pipelines: dict[str, NlpPipeline]
    fallback: NlpPipeline

    def route(self, language_tag: str | None) -> NlpPipeline:
        """
        Decide which NLP pipeline should be used based on the language tag.
        Prioritized routes: Hungarian (HuSpaCy), English/Spanish (spaCy), fallback (Stanza/other).
        """
        lang_code = (language_tag or "").split("-")[0].lower()
        if lang_code.startswith("hu") and "huspacy" in self.pipelines:
            return self.pipelines["huspacy"]
        if lang_code in {"en", "es"} and f"spacy_{lang_code}" in self.pipelines:
            return self.pipelines[f"spacy_{lang_code}"]
        return self.fallback
