from __future__ import annotations

TOPIC_RULES_DE: dict[str, tuple[str, ...]] = {
    "finance": ("rechnung", "zahlung", "faktura", "invoice"),
    "sales": ("kunde", "onboarding", "crm", "hubspot"),
    "support": ("ticket", "support", "fehler", "problem"),
    "operations": ("büro", "berlin", "standort", "niederlassung"),
}

__all__ = ["TOPIC_RULES_DE"]
