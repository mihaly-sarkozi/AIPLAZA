"""
Language detection utilities: whole-text and chunk-level (sentence) for mixed-language content.
"""
from __future__ import annotations

import re
from typing import List, Tuple

# Sentence-ending punctuation for chunk split
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+|\n+")


def detect_language(text: str) -> str:
    """Detect language for whole text: en, hu, es or fallback en."""
    if not text or not text.strip():
        return "en"
    try:
        import langdetect
        lang = langdetect.detect(text)
        if lang in ("hu", "es"):
            return lang
        return "en"
    except Exception:
        return "en"


def detect_language_per_chunk(
    text: str,
    chunk_strategy: str = "sentence",
    max_chunk_chars: int = 500,
) -> List[Tuple[int, int, str]]:
    """
    Detect language per chunk (sentence or fixed size). Returns list of (start, end, lang).
    Enables NER to run with the correct language for mixed-language documents.
    """
    if not text or not text.strip():
        return [(0, len(text), "en")]

    chunks: List[Tuple[int, int]] = []
    if chunk_strategy == "sentence":
        last = 0
        for m in _SENTENCE_END.finditer(text):
            start, end = last, m.start()
            if end > start and (end - start) >= 10:
                chunks.append((start, end))
            last = m.end()
        if last < len(text):
            chunks.append((last, len(text)))
        # Merge very short chunks with next
        merged: List[Tuple[int, int]] = []
        i = 0
        while i < len(chunks):
            s, e = chunks[i]
            while i + 1 < len(chunks) and (e - s) < 30:
                i += 1
                _, e = chunks[i]
            merged.append((s, e))
            i += 1
        chunks = merged
    else:
        # Fixed-size chunks
        for i in range(0, len(text), max_chunk_chars):
            chunks.append((i, min(i + max_chunk_chars, len(text))))

    result: List[Tuple[int, int, str]] = []
    try:
        import langdetect
        for start, end in chunks:
            chunk_text = text[start:end].strip()
            if len(chunk_text) < 5:
                result.append((start, end, "en"))
                continue
            try:
                lang = langdetect.detect(chunk_text)
                if lang not in ("hu", "es"):
                    lang = "en"
            except Exception:
                lang = "en"
            result.append((start, end, lang))
    except ImportError:
        result = [(s, e, "en") for s, e in chunks]
    return result
