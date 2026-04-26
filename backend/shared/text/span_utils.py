from __future__ import annotations

from typing import List, Tuple


def deduplicate_matches_longer_wins(
    matches: List[Tuple[int, int, str, str]],
) -> List[Tuple[int, int, str, str]]:
    if not matches:
        return []

    by_len = sorted(
        matches,
        key=lambda match: (-(match[1] - match[0]), match[0]),
    )
    kept: List[Tuple[int, int, str, str]] = []
    for start, end, data_type, value in by_len:
        if any(saved_start < end and saved_end > start for saved_start, saved_end, _, _ in kept):
            continue
        kept.append((start, end, data_type, value))
    return sorted(kept, key=lambda match: match[0])
