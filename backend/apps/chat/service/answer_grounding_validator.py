from __future__ import annotations

from typing import Any


class AnswerGroundingValidator:
    NO_EVIDENCE_ANSWER = "Nem találtam releváns választ a kiválasztott tudástárban."
    NOT_READY_ANSWER = "A kiválasztott tudástár még nem kereshető. Az indexelés vagy ellenőrzés nem fejeződött be."

    def validate(self, *, packet: dict[str, Any], answer: str) -> dict[str, Any]:
        answer_mode = str(packet.get("answer_mode") or "").upper()
        if answer_mode == "BLOCKED_NOT_READY":
            return {
                "answer": self.NOT_READY_ANSWER,
                "answer_mode": "BLOCKED_NOT_READY",
                "blocked": True,
                "allow_llm": False,
            }

        context_blocks = packet.get("context_blocks") or []
        citations = packet.get("citations") or []
        sources = packet.get("sources") or []

        if answer_mode == "NO_ANSWER" or not context_blocks or (not citations and not sources):
            return {
                "answer": self.NO_EVIDENCE_ANSWER,
                "answer_mode": "NO_ANSWER",
                "blocked": True,
                "allow_llm": False,
            }

        if not str(answer or "").strip():
            return {
                "answer": self.NO_EVIDENCE_ANSWER,
                "answer_mode": "NO_ANSWER",
                "blocked": True,
                "allow_llm": False,
            }

        warning = None
        if not sources:
            warning = "missing_sources"

        return {
            "answer": answer,
            "answer_mode": "ANSWERED",
            "blocked": False,
            "allow_llm": True,
            "warning": warning,
        }


__all__ = ["AnswerGroundingValidator"]
