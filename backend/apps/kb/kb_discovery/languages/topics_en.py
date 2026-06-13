from __future__ import annotations

TOPIC_RULES_EN: dict[str, tuple[str, ...]] = {
    "sales": ("customer", "onboarding", "crm", "hubspot", "lead"),
    "finance": ("invoice", "billing", "payment", "receipt"),
    "support": ("ticket", "support", "issue", "error"),
    "operations": ("office", "london", "location", "site"),
}

__all__ = ["TOPIC_RULES_EN"]
