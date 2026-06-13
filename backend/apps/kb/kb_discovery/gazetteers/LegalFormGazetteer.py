from __future__ import annotations

import re

from apps.kb.kb_discovery.gazetteers.data_paths import data_file
from apps.kb.kb_discovery.gazetteers.loaders import load_json

_WORD_CHAR = r"\wÁÉÍÓÖŐÚÜŰáéíóöőúüű"
_NOT_AFTER_SUFFIX = rf"(?![{_WORD_CHAR}.])"


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

    def forms_for_language(self, language_code: str | None) -> tuple[str, ...]:
        code = (language_code or "").strip().lower()
        if code in self._forms_by_language:
            return tuple(
                dict.fromkeys(
                    list(self._forms_by_language[code]) + list(self._forms_by_language["global"])
                )
            )
        return self._all_forms

    def suffix_group_for_language(self, language_code: str | None) -> str:
        forms = self.forms_for_language(language_code)
        escaped = sorted({re.escape(form) for form in forms}, key=len, reverse=True)
        return "|".join(escaped)

    def company_pattern_for_language(self, language_code: str | None) -> re.Pattern[str]:
        suffix_group = self.suffix_group_for_language(language_code)
        name_token = rf"[A-ZÁÉÍÓÖŐÚÜŰ0-9][{_WORD_CHAR}\-]*"
        return re.compile(
            rf"(?<![{_WORD_CHAR}])((?:{name_token}(?:\s+{name_token})*)(?:\s+|,\s+)(?:{suffix_group})){_NOT_AFTER_SUFFIX}",
            re.UNICODE | re.IGNORECASE,
        )


__all__ = ["LegalFormGazetteer"]
