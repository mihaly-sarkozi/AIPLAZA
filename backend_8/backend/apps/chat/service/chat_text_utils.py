# backend/apps/chat/service/chat_text_utils.py
# Feladat: A ChatService állapotmentes szöveg-, debug- és LLM response helper függvényeit tartalmazza. Prompt méretbecslést, response text kinyerést, debug sanitizationt, history context építést és alap token normalizálást választ le a nagy chat service-ről. Program-specifikus chat utility réteg.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from typing import Any
import re
import unicodedata


def fold_lexicon_token(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(ch for ch in normalized if not unicodedata.combining(ch)).lower().strip()


def coerce_response_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (list, tuple)):
        parts: list[str] = []
        for item in value:
            if isinstance(item, str):
                text = item.strip()
                if text:
                    parts.append(text)
                continue
            if isinstance(item, dict):
                for key in ("text", "content", "reasoning"):
                    raw = item.get(key)
                    if isinstance(raw, str) and raw.strip():
                        parts.append(raw.strip())
                        break
        return "\n".join(part for part in parts if part).strip()
    if isinstance(value, dict):
        for key in ("text", "content", "reasoning", "summary"):
            raw = value.get(key)
            if isinstance(raw, str) and raw.strip():
                return raw.strip()
        return ""
    return str(value).strip()


def extract_response_text(response: Any) -> str:
    choices = getattr(response, "choices", None) or []
    if not choices:
        return ""
    message = getattr(choices[0], "message", None)
    if message is None:
        return ""
    if isinstance(message, dict):
        for key in ("content", "reasoning", "output_text"):
            text = coerce_response_text(message.get(key))
            if text:
                return text
        return ""
    for key in ("content", "reasoning", "output_text"):
        text = coerce_response_text(getattr(message, key, None))
        if text:
            return text
    return ""


def estimate_prompt_chars(
    *,
    question: str,
    conversation_history: list[dict[str, str]] | None,
    retrieval_history: list[str] | None,
) -> int:
    total = len(str(question or ""))
    total += sum(
        len(str(item.get("content") or item.get("text") or ""))
        for item in (conversation_history or [])
        if isinstance(item, dict)
    )
    total += sum(len(str(item or "")) for item in (retrieval_history or []))
    return max(1, total)


def dedupe_keep_order(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = " ".join(str(value or "").strip().split())
        if not item:
            continue
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def fold_text(value: str | None) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    return "".join(char for char in normalized if not unicodedata.combining(char)).lower()


def sanitize_debug_text(value: Any) -> str:
    text = str(value or "")
    if not text:
        return ""
    text = re.sub(r"(?i)\b[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}\b", "[redacted_email]", text)
    text = re.sub(r"\b(?:\+?\d[\d\s().-]{6,}\d)\b", "[redacted_phone]", text)
    text = re.sub(r"\b\d{6,}\b", "[redacted_number]", text)
    return text[:400] + ("..." if len(text) > 400 else "")


def sanitize_debug_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): sanitize_debug_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [sanitize_debug_value(v) for v in value]
    if isinstance(value, tuple):
        return [sanitize_debug_value(v) for v in value]
    if isinstance(value, str):
        return sanitize_debug_text(value)
    return value


def conversation_history_context(
    conversation_history: list[dict[str, str]] | None,
    *,
    max_messages: int,
    max_chars: int,
) -> str:
    if not conversation_history:
        return ""
    rows: list[str] = []
    total = 0
    for item in reversed(conversation_history[-max_messages:]):
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or "").strip().lower()
        if role not in {"user", "assistant"}:
            continue
        text = " ".join(str(item.get("content") or item.get("text") or "").strip().split())
        if not text:
            continue
        prefix = "Felhasználó" if role == "user" else "Asszisztens"
        line = f"{prefix}: {text[:1200]}"
        if total + len(line) > max_chars:
            break
        rows.append(line)
        total += len(line)
    rows.reverse()
    return "\n".join(rows)


def retrieval_history_context(
    retrieval_history: list[str] | None,
    *,
    max_items: int,
    max_chars: int,
) -> str:
    if not retrieval_history:
        return ""
    rows: list[str] = []
    total = 0
    for item in retrieval_history[:max_items]:
        text = " ".join(str(item or "").strip().split())
        if not text:
            continue
        line = f"- {text[:300]}"
        if total + len(line) > max_chars:
            break
        rows.append(line)
        total += len(line)
    return "\n".join(rows)


__all__ = [
    "coerce_response_text",
    "conversation_history_context",
    "dedupe_keep_order",
    "estimate_prompt_chars",
    "extract_response_text",
    "fold_lexicon_token",
    "fold_text",
    "retrieval_history_context",
    "sanitize_debug_text",
    "sanitize_debug_value",
]
