from __future__ import annotations

TOPIC_RULES_HU: dict[str, tuple[str, ...]] = {
    "finance": ("számla", "számlázás", "fizetés", "díjbekérő", "rechnung"),
    "sales": ("ügyfél", "crm", "hubspot", "onboarding", "lead"),
    "support": ("hiba", "ticket", "support", "panasz"),
    "operations": ("iroda", "budapest", "helyszín", "telephely"),
}

__all__ = ["TOPIC_RULES_HU"]
