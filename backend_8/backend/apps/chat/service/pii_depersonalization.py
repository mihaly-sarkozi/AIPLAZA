from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any
from collections.abc import Iterable

logger = logging.getLogger(__name__)

_TOKEN_RE = re.compile(r"\[[a-z0-9_]+_\d+\]")


@dataclass(frozen=True)
class EncodedPiiText:
    text: str
    mappings: list[dict[str, Any]]


@dataclass(frozen=True)
class RehydratedPiiText:
    text: str
    restored_spans: list[dict[str, Any]]


class PiiDepersonalizationService:
    def __init__(self, mapping_repo: Any, detector: Any | None = None) -> None:
        self._mapping_repo = mapping_repo
        self._detector = detector

    def encode_text(
        self,
        *,
        corpus_uuid: str,
        text: str,
        enabled: bool,
        sensitivity: str = "medium",
    ) -> EncodedPiiText:
        if not enabled:
            return EncodedPiiText(text=str(text or ""), mappings=[])
        raw = str(text or "")
        if not raw.strip():
            return EncodedPiiText(text=raw, mappings=[])
        if not callable(self._detector):
            return EncodedPiiText(text=raw, mappings=[])
        try:
            matches = self._detector(raw, sensitivity or "medium")
        except Exception:
            logger.warning("PII encode detect failed; fallback no-op.", exc_info=True)
            return EncodedPiiText(text=raw, mappings=[])
        if not matches:
            return EncodedPiiText(text=raw, mappings=[])

        encoded = raw
        mappings: list[dict[str, Any]] = []
        replacements: list[tuple[int, int, str, str, str]] = []
        for start, end, entity_type, value in sorted(matches, key=lambda item: item[0], reverse=True):
            token = self._mapping_repo.resolve_or_create_token(
                corpus_uuid=corpus_uuid,
                entity_type=str(entity_type or "pii"),
                original_value=str(value or ""),
            )
            if not token:
                continue
            replacements.append((int(start), int(end), token, str(entity_type or "pii"), str(value or "")))
        for start, end, token, entity_type, value in replacements:
            encoded = f"{encoded[:start]}{token}{encoded[end:]}"
            mappings.append({"token": token, "entity_type": entity_type, "original_preview": value[:80]})
        return EncodedPiiText(text=encoded, mappings=list(reversed(mappings)))

    def rehydrate_text(
        self,
        *,
        corpus_uuid: str,
        text: str,
        enabled: bool,
        allowed_tokens: Iterable[str] | None = None,
    ) -> RehydratedPiiText:
        raw = str(text or "")
        if not enabled or not raw:
            return RehydratedPiiText(text=raw, restored_spans=[])
        allowed: set[str] | None = None
        if allowed_tokens is not None:
            allowed = {str(token or "").strip() for token in allowed_tokens if str(token or "").strip()}
            if not allowed:
                return RehydratedPiiText(text=raw, restored_spans=[])
        token_matches = list(_TOKEN_RE.finditer(raw))
        if not token_matches:
            return RehydratedPiiText(text=raw, restored_spans=[])
        if allowed is not None:
            token_matches = [match for match in token_matches if match.group(0) in allowed]
            if not token_matches:
                return RehydratedPiiText(text=raw, restored_spans=[])
        token_values = self._mapping_repo.resolve_tokens(
            corpus_uuid=corpus_uuid,
            tokens=[match.group(0) for match in token_matches],
        )
        if not token_values:
            return RehydratedPiiText(text=raw, restored_spans=[])

        chunks: list[str] = []
        restored_spans: list[dict[str, Any]] = []
        cursor = 0
        output_len = 0
        for match in token_matches:
            token = match.group(0)
            replacement = token_values.get(token)
            if replacement is None:
                continue
            prefix = raw[cursor : match.start()]
            chunks.append(prefix)
            output_len += len(prefix)
            chunks.append(replacement)
            start = output_len
            output_len += len(replacement)
            restored_spans.append(
                {
                    "start": start,
                    "end": output_len,
                    "token": token,
                    "value": replacement,
                    "entity_type": token.strip("[]").split("_", 1)[0],
                }
            )
            cursor = match.end()
        chunks.append(raw[cursor:])
        return RehydratedPiiText(text="".join(chunks), restored_spans=restored_spans)

    def detect_plain_spans(
        self,
        *,
        text: str,
        enabled: bool,
        sensitivity: str = "medium",
    ) -> list[dict[str, Any]]:
        raw = str(text or "")
        if not enabled or not raw.strip():
            return []
        if not callable(self._detector):
            return []
        try:
            matches = self._detector(raw, sensitivity or "medium")
        except Exception:
            logger.warning("PII plain span detection failed; fallback no-op.", exc_info=True)
            return []
        if not matches:
            return []
        spans: list[dict[str, Any]] = []
        for start, end, entity_type, value in sorted(matches, key=lambda item: (int(item[0]), int(item[1]))):
            try:
                safe_start = max(0, min(len(raw), int(start)))
                safe_end = max(safe_start, min(len(raw), int(end)))
            except Exception:
                continue
            if safe_end <= safe_start:
                continue
            if spans and safe_start < int(spans[-1]["end"]):
                # Átfedő spaneket ne duplikáljunk, maradjon a korábbi találat.
                continue
            spans.append(
                {
                    "start": safe_start,
                    "end": safe_end,
                    "token": None,
                    "value": str(value or raw[safe_start:safe_end]),
                    "entity_type": str(entity_type or "pii"),
                }
            )
        return spans


__all__ = [
    "EncodedPiiText",
    "PiiDepersonalizationService",
    "RehydratedPiiText",
]
