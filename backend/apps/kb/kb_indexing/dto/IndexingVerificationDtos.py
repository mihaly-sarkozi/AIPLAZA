from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class QdrantVerificationResult:
    verification_id: str
    status: str
    error_code: str | None
    error_message: str | None
    collection_name: str
    expected_points: int
    verified_points: int
    missing_points: int
    payload_mismatches: int
    vector_hash_mismatches: int
    failed_points: int
    issue_codes: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class SearchReadinessResult:
    ready_for_search: bool
    qdrant_verified: bool
    blocked_reasons: tuple[str, ...] = field(default_factory=tuple)
    metadata: dict[str, Any] = field(default_factory=dict)


__all__ = ["QdrantVerificationResult", "SearchReadinessResult"]
