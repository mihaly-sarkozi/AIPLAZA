from __future__ import annotations

from dataclasses import dataclass

from .candidate_consolidator import merge_or_split_adjacent_candidates
from .claim_candidate_scorer import collect_reasons, score_claim
from .claim_span_builder import build_claim_span
from .complement_finder import find_local_complements
from .language_router import LanguageRouter
from .predicate_finder import find_predicate_heads
from .subject_finder import find_best_subject
from .types import ClaimCandidate, ComplementHints, ParsedDoc


def _best_object(complements: ComplementHints) -> str | None:
    if complements.objects:
        return complements.objects[0].text
    if complements.attributes:
        return complements.attributes[0].text
    return None


@dataclass
class ClaimFineSplitter:
    language_router: LanguageRouter

    def split_block(
        self,
        block_text: str,
        language_tag: str | None = None,
    ) -> list[ClaimCandidate]:
        pipeline = self.language_router.route(language_tag)
        doc = pipeline(block_text)
        return self.split_doc(doc)

    def split_doc(self, doc: ParsedDoc) -> list[ClaimCandidate]:
        predicate_heads = find_predicate_heads(doc)
        candidates: list[ClaimCandidate] = []
        for pred in predicate_heads:
            subject = find_best_subject(pred, doc)
            complements = find_local_complements(pred, doc)
            span = build_claim_span(pred, subject, complements, doc)
            span_start_char, span_end_char = span.char_bounds(doc)
            candidate = ClaimCandidate(
                text_span=span.text(doc),
                subject_hint=subject.text if subject else None,
                predicate_hint=pred.lemma,
                object_hint=_best_object(complements),
                start_token=span.start,
                end_token=span.end,
                char_start=span_start_char,
                char_end=span_end_char,
                confidence=score_claim(span, pred, subject, complements),
                split_reason=collect_reasons(pred, subject, complements),
            )
            candidates.append(candidate)
        return merge_or_split_adjacent_candidates(candidates, doc)
