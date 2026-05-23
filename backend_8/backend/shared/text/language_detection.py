# backend/shared/text/language_detection.py
# Feladat: Egyszerű dokumentum- és chunk-szintű nyelvdetektálást ad. A langdetect könyvtárat opcionálisan használja, támogatott nyelveknél hu/es eredményt ad, minden más vagy hiba esetén en fallbacket választ. Shared text helper PII és knowledge pipeline-okhoz.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

import re
from typing import List, Tuple

_SENTENCE_END = re.compile(r"(?<=[.!?])\s+|\n+")
_SUPPORTED_LANGUAGE_CODES = {"hu", "es"}
_DEFAULT_LANGUAGE_CODE = "en"


def detect_language(text: str) -> str:
    if not text or not text.strip():
        return _DEFAULT_LANGUAGE_CODE
    try:
        import langdetect

        lang = langdetect.detect(text)
        if lang in _SUPPORTED_LANGUAGE_CODES:
            return lang
        return _DEFAULT_LANGUAGE_CODE
    except Exception:
        return _DEFAULT_LANGUAGE_CODE


def detect_language_per_chunk(
    text: str,
    chunk_strategy: str = "sentence",
    max_chunk_chars: int = 500,
) -> List[Tuple[int, int, str]]:
    if not text or not text.strip():
        return [(0, len(text), _DEFAULT_LANGUAGE_CODE)]

    chunks: List[Tuple[int, int]] = []
    if chunk_strategy == "sentence":
        last = 0
        for match in _SENTENCE_END.finditer(text):
            start, end = last, match.start()
            if end > start and (end - start) >= 10:
                chunks.append((start, end))
            last = match.end()
        if last < len(text):
            chunks.append((last, len(text)))

        merged: List[Tuple[int, int]] = []
        i = 0
        while i < len(chunks):
            start, end = chunks[i]
            while i + 1 < len(chunks) and (end - start) < 30:
                i += 1
                _, end = chunks[i]
            merged.append((start, end))
            i += 1
        chunks = merged
    else:
        for i in range(0, len(text), max_chunk_chars):
            chunks.append((i, min(i + max_chunk_chars, len(text))))

    result: List[Tuple[int, int, str]] = []
    try:
        import langdetect

        for start, end in chunks:
            chunk_text = text[start:end].strip()
            if len(chunk_text) < 5:
                result.append((start, end, _DEFAULT_LANGUAGE_CODE))
                continue
            try:
                lang = langdetect.detect(chunk_text)
                if lang not in _SUPPORTED_LANGUAGE_CODES:
                    lang = _DEFAULT_LANGUAGE_CODE
            except Exception:
                lang = _DEFAULT_LANGUAGE_CODE
            result.append((start, end, lang))
    except ImportError:
        result = [(start, end, _DEFAULT_LANGUAGE_CODE) for start, end in chunks]

    return result
