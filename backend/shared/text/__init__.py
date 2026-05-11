from shared.text.chunking import chunk_text_for_training
from shared.text.language_detection import detect_language, detect_language_per_chunk
from shared.text.language_lexicon import get_lexicon_terms, normalize_lexicon_language, validate_language_lexicon
from shared.text.span_utils import deduplicate_matches_longer_wins

__all__ = [
    "chunk_text_for_training",
    "deduplicate_matches_longer_wins",
    "detect_language",
    "detect_language_per_chunk",
    "get_lexicon_terms",
    "normalize_lexicon_language",
    "validate_language_lexicon",
]
