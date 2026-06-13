from __future__ import annotations

import re

from apps.kb.kb_discovery.gazetteers.data_paths import data_file
from apps.kb.kb_discovery.gazetteers.loaders import load_json


class LegalFormGazetteer:
    def __init__(self) -> None:
        self._forms_by_language: dict[str, tuple[str, ...]] = {}
        for code in ("hu", "en", "es", "global"):
            values = load_json(data_file("legal_forms", f"legal_forms_{code}.json"), [])
            self._forms_by_language[code] = tuple(
                str(item).strip() for item in values if str(item).strip()
            )
        self._all_forms = tuple(
            dict.fromkeys(
                form
                for forms in self._forms_by_language.values()
                for form in forms
            )
        )
        escaped = sorted({re.escape(form) for form in self._all_forms}, key=len, reverse=True)
        self._suffix_pattern = re.compile(
            rf"\b({'|'.join(escaped)})\b",
            re.IGNORECASE,
        )

    def forms_for_language(self, language_code: str | None) -> tuple[str, ...]:
        code = (language_code or "").strip().lower()
        if code in self._forms_by_language:
            return self._forms_by_language[code] + self._forms_by_language["global"]
        return self._all_forms

    @property
    def suffix_pattern(self) -> re.Pattern[str]:
        return self._suffix_pattern


__all__ = ["LegalFormGazetteer"]
