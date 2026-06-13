from __future__ import annotations


class TopicDictionaryProvider:
    def rules(self) -> dict[str, tuple[str, ...]]:
        return {
            "sales": ("crm", "hubspot", "lead", "ügyfél", "onboarding"),
            "finance": ("számla", "fizetés", "díjbekérő", "invoice"),
            "support": ("hiba", "ticket", "support"),
        }


__all__ = ["TopicDictionaryProvider"]
