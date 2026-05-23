# backend/apps/chat/application/chat_payload_policy.py
# Feladat: Chat HTTP/channel kérés payload limitjeit, normalizálását és debug/budget helper logikáját tartalmazza. Tenant csomag alapján számol kérdés-, history-, retrieval- és forráslimiteket, majd a route-ok előtt validál és rövidít. Program-specifikus chat API policy helper.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

import re
from typing import Any

from fastapi import HTTPException

from core.kernel.config.config_loader import get_app_env, settings
from core.kernel.config.environment import is_production_env
from core.modules.users.domain.dto import User


def tenant_chat_limits(tenant) -> dict[str, int | bool]:
    config = getattr(tenant, "config", None)
    flags = getattr(config, "feature_flags", None) or {}
    package = str(getattr(config, "package", "") or "").strip().lower()
    is_demo = bool(flags.get("demo_mode"))
    is_starter = package == "starter"
    try:
        env = get_app_env()
    except Exception:
        env = "dev"
    if is_demo:
        return {
            "max_question_chars": max(64, int(getattr(settings, "chat_demo_max_question_chars", 1024) or 1024)),
            "max_history_items": max(0, int(getattr(settings, "chat_demo_max_history_items", 8) or 8)),
            "max_history_chars": max(0, int(getattr(settings, "chat_demo_max_history_chars", 2400) or 2400)),
            "max_retrieval_items": max(0, int(getattr(settings, "chat_demo_max_retrieval_items", 6) or 6)),
            "max_retrieval_chars": max(0, int(getattr(settings, "chat_demo_max_retrieval_chars", 1800) or 1800)),
            "max_sources": max(1, int(getattr(settings, "chat_demo_max_sources", 3) or 3)),
            "allow_debug": bool(getattr(settings, "chat_demo_allow_debug", False)) or not is_production_env(env),
            "channel_daily_limit_cap": max(1, int(getattr(settings, "channel_demo_max_daily_limit", 100) or 100)),
            "channel_per_minute_limit_cap": max(1, int(getattr(settings, "channel_demo_max_per_minute_limit", 10) or 10)),
            "budget_scope": "demo",
        }
    default_sources = max(1, int(getattr(settings, "chat_default_max_sources", 8) or 8))
    return {
        "max_question_chars": max(64, int(getattr(settings, "chat_max_input_chars", 2400) or 2400)),
        "max_history_items": max(0, int(getattr(settings, "chat_max_history_items", 30) or 30)),
        "max_history_chars": max(0, int(getattr(settings, "chat_max_history_chars", 12000) or 12000)),
        "max_retrieval_items": max(0, int(getattr(settings, "chat_max_retrieval_items", 20) or 20)),
        "max_retrieval_chars": max(0, int(getattr(settings, "chat_max_retrieval_chars", 6000) or 6000)),
        "max_sources": max(1, int(getattr(settings, "chat_starter_max_sources", 5) or 5)) if is_starter else default_sources,
        "allow_debug": True,
        "channel_daily_limit_cap": max(1, int(getattr(settings, "channel_default_max_daily_limit", 5000) or 5000)),
        "channel_per_minute_limit_cap": max(1, int(getattr(settings, "channel_default_max_per_minute_limit", 120) or 120)),
        "budget_scope": "starter" if is_starter else "default",
    }


def validate_chat_payload_or_413(req, *, limits: dict[str, int | bool]) -> None:
    question = str(getattr(req, "question", "") or "")
    if len(question) > int(limits["max_question_chars"]):
        raise HTTPException(status_code=413, detail="A kérdés túl hosszú ehhez a csomaghoz.")
    conversation_history = list(getattr(req, "conversation_history", []) or [])
    retrieval_history = list(getattr(req, "retrieval_history", []) or [])
    if len(conversation_history) > int(limits["max_history_items"]):
        raise HTTPException(status_code=413, detail="Túl sok conversation history elem.")
    if len(retrieval_history) > int(limits["max_retrieval_items"]):
        raise HTTPException(status_code=413, detail="Túl sok retrieval history elem.")
    history_chars = 0
    for row in conversation_history:
        if isinstance(row, dict):
            history_chars += len(str(row.get("content") or row.get("text") or ""))
    retrieval_chars = sum(len(str(item or "")) for item in retrieval_history)
    if history_chars > int(limits["max_history_chars"]):
        raise HTTPException(status_code=413, detail="A conversation history mérete túl nagy ehhez a csomaghoz.")
    if retrieval_chars > int(limits["max_retrieval_chars"]):
        raise HTTPException(status_code=413, detail="A retrieval history mérete túl nagy ehhez a csomaghoz.")


def split_sentences(text: str) -> list[str]:
    parts = re.findall(r"[^.!?]+[.!?]?", str(text or ""))
    return [part.strip() for part in parts if part and part.strip()]


def normalize_chat_payload(req, *, limits: dict[str, int | bool]) -> None:
    question = str(getattr(req, "question", "") or "").strip()
    question_words = re.findall(r"[A-Za-zÁÉÍÓÖŐÚÜŰáéíóöőúüű0-9]+", question)
    question_sentences = split_sentences(question)
    if len(question_sentences) > 4 or len(question_words) > 30:
        raise HTTPException(status_code=422, detail="Egyszerre csak egy rövid mondatra tudok válaszolni.")
    if len(question_sentences) > 2:
        question = " ".join(question_sentences[:2]).strip()
    max_question_chars = int(limits["max_question_chars"])
    if len(question) > max_question_chars:
        question = question[:max_question_chars].rstrip()
    req.question = question

    conversation_history = list(getattr(req, "conversation_history", []) or [])
    max_history_items = int(limits["max_history_items"])
    max_history_chars = int(limits["max_history_chars"])
    if len(conversation_history) > max_history_items:
        conversation_history = conversation_history[-max_history_items:]
    while conversation_history:
        history_chars = sum(len(str((row or {}).get("content") or (row or {}).get("text") or "")) for row in conversation_history if isinstance(row, dict))
        if history_chars <= max_history_chars:
            break
        conversation_history = conversation_history[1:]
    req.conversation_history = conversation_history

    retrieval_history = list(getattr(req, "retrieval_history", []) or [])
    max_retrieval_items = int(limits["max_retrieval_items"])
    max_retrieval_chars = int(limits["max_retrieval_chars"])
    if len(retrieval_history) > max_retrieval_items:
        retrieval_history = retrieval_history[-max_retrieval_items:]
    while retrieval_history and sum(len(str(item or "")) for item in retrieval_history) > max_retrieval_chars:
        retrieval_history = retrieval_history[1:]
    req.retrieval_history = retrieval_history


def debug_responses_globally_enabled() -> bool:
    enabled = bool(getattr(settings, "chat_debug_responses_enabled", True))
    try:
        env = get_app_env()
    except Exception:
        env = "dev"
    if is_production_env(env) and not enabled:
        return False
    return enabled


def effective_debug_for_user(*, requested: bool, user: User, limits: dict[str, int | bool]) -> bool:
    if not requested:
        return False
    if not debug_responses_globally_enabled():
        return False
    if not bool(limits.get("allow_debug")):
        return False
    return bool(getattr(user, "id", None))


def normalize_budget_result(raw: Any) -> tuple[bool, str, dict[str, Any] | None]:
    if isinstance(raw, tuple) and len(raw) == 3:
        return bool(raw[0]), str(raw[1] or ""), raw[2] if isinstance(raw[2], dict) or raw[2] is None else None
    if raw is None:
        return True, "", None
    if isinstance(raw, bool):
        return raw, "", None
    if isinstance(raw, dict):
        return True, "", raw
    return True, "", None


__all__ = [
    "effective_debug_for_user",
    "normalize_budget_result",
    "normalize_chat_payload",
    "tenant_chat_limits",
    "validate_chat_payload_or_413",
]
