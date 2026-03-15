from __future__ import annotations

from typing import Any


def build_structural_chunks(
    sentences: list[dict[str, Any]],
    min_tokens: int = 350,
    target_tokens: int = 520,
    max_tokens: int = 700,
    overlap_ratio: float = 0.12,
) -> list[dict[str, Any]]:
    """350-700 token körüli chunkok mondathatáron, mérsékelt overlap-pel."""
    if not sentences:
        return []
    chunks: list[dict[str, Any]] = []
    idx = 0
    chunk_order = 0
    overlap = max(1, int((target_tokens * overlap_ratio)))

    while idx < len(sentences):
        token_sum = 0
        selected: list[dict[str, Any]] = []
        start_idx = idx
        while idx < len(sentences):
            s = sentences[idx]
            next_sum = token_sum + int(s["token_count"])
            if selected and next_sum > max_tokens:
                break
            selected.append(s)
            token_sum = next_sum
            idx += 1
            if token_sum >= target_tokens:
                break

        if not selected:
            idx += 1
            continue

        chunks.append(
            {
                "chunk_order": chunk_order,
                "text": " ".join(s["sanitized_text"] for s in selected).strip(),
                "sentence_ids": [int(s["id"]) for s in selected if s.get("id") is not None],
                "assertion_ids": [],
                "entity_ids": [],
                "predicate_hints": [],
                "token_count": token_sum,
                "time_from": None,
                "time_to": None,
                "place_keys": [],
            }
        )
        chunk_order += 1

        if idx >= len(sentences):
            break

        if token_sum >= min_tokens:
            back_tokens = 0
            back = idx - 1
            while back > start_idx and back_tokens < overlap:
                back_tokens += int(sentences[back]["token_count"])
                back -= 1
            idx = max(start_idx + 1, back + 1)

    return chunks
