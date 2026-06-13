from __future__ import annotations

TOPIC_RULES_ES: dict[str, tuple[str, ...]] = {
    "finance": ("factura", "pago", "invoice", "cobro"),
    "sales": ("cliente", "onboarding", "crm", "hubspot"),
    "support": ("ticket", "support", "error", "problema"),
    "operations": ("oficina", "madrid", "sede", "filial"),
}

__all__ = ["TOPIC_RULES_ES"]
