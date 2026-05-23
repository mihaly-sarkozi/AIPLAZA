# backend/shared/text/chunking.py
# Feladat: Hosszabb szövegek tréninghez vagy ingesthez használható darabolását végzi. A bemenetet normalizálja, bekezdés- és mondathatárok mentén bontja, majd túl hosszú mondatoknál fix méretű szeletekre esik vissza. Shared text helper knowledge ingest és runtime store folyamatokhoz.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

import re


def chunk_text_for_training(text: str, max_chunk: int = 900) -> list[str]:
    raw = " ".join(str(text or "").split())
    if not raw:
        return []

    parts: list[str] = []
    for para in re.split(r"\n\s*\n", raw):
        para = para.strip()
        if not para:
            continue
        if len(para) <= max_chunk:
            parts.append(para)
            continue

        sentences = re.split(r"(?<=[.!?])\s+", para)
        buf = ""
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            if len(buf) + len(sentence) + 1 <= max_chunk:
                buf = f"{buf} {sentence}".strip()
            else:
                if buf:
                    parts.append(buf)
                if len(sentence) <= max_chunk:
                    buf = sentence
                else:
                    for i in range(0, len(sentence), max_chunk):
                        parts.append(sentence[i : i + max_chunk])
                    buf = ""
        if buf:
            parts.append(buf)

    return [part for part in parts if len(part.strip()) > 20]
