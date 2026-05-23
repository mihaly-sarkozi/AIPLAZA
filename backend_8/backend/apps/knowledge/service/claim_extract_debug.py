"""ClaimExtractorV1: konzolos debug kimenet."""
from __future__ import annotations

from apps.knowledge.domain.claim import Claim
from apps.knowledge.domain.sentence import Sentence
from apps.knowledge.service.claim_extract_normalize import sentence_text
from apps.knowledge.service.language_rules import resolve_language


def debug_print(sentence: Sentence, claims: list[Claim], language: str | None = None) -> None:
    resolved_language = resolve_language(
        text=sentence.text_content,
        language=language or sentence.metadata.get("language") or sentence.metadata.get("language_tag"),
    )
    print(f"[CLAIM DEBUG] language={resolved_language} sentence={sentence_text(sentence)}")
    for claim in claims:
        md = claim.metadata or {}
        ep = md.get("extraction_pattern") or md.get("pattern_name")
        el = md.get("extraction_language") or md.get("language")
        if ep is not None or el is not None:
            print(f"   extraction_pattern={ep} extraction_language={el}")
        print("  ", claim.debug_repr())
