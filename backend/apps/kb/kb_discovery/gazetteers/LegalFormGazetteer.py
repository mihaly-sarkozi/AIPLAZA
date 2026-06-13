from __future__ import annotations

import re

from apps.kb.kb_discovery.gazetteers.data_paths import data_file
from apps.kb.kb_discovery.gazetteers.loaders import load_json

_WORD_CHAR = r"\wÁÉÍÓÖŐÚÜŰáéíóöőúüű"
_NOT_AFTER_SUFFIX = rf"(?![{_WORD_CHAR}.])"

_CURATED_SUFFIXES: dict[str, tuple[str, ...]] = {
    "hu": (
        "Kft.",
        "Kft",
        "Bt.",
        "Bt",
        "Zrt.",
        "Zrt",
        "Nyrt.",
        "Nyrt",
        "Kkt.",
        "Kkt",
        "Rt.",
        "Rt",
    ),
    "en": (
        "LLC",
        "L.L.C.",
        "Ltd.",
        "Ltd",
        "Limited",
        "Inc.",
        "Inc",
        "Corp.",
        "Corporation",
        "PLC",
        "LLP",
    ),
    "es": (
        "S.L.",
        "SL",
        "S.L.U.",
        "S.A.",
        "SA",
        "Sociedad Limitada",
        "Sociedad Anónima",
    ),
    "global": (
        "GmbH",
        "AG",
        "B.V.",
        "N.V.",
        "S.à r.l.",
        "Pty Ltd",
        "Pte. Ltd.",
        "SRL",
        "SpA",
    ),
}


class LegalFormGazetteer:
    def __init__(self) -> None:
        self._suffixes_by_language: dict[str, tuple[str, ...]] = {}
        self._full_names_by_language: dict[str, tuple[str, ...]] = {}
        for code in ("hu", "en", "es", "global"):
            suffix_path = data_file("legal_forms", f"legal_form_suffixes_{code}.json")
            full_path = data_file("legal_forms", f"legal_form_full_names_{code}.json")
            legacy_path = data_file("legal_forms", f"legal_forms_{code}.json")

            suffix_values = load_json(suffix_path, [])
            full_values = load_json(full_path, [])
            if not full_values:
                full_values = load_json(legacy_path, [])

            suffixes = tuple(
                dict.fromkeys(
                    list(_CURATED_SUFFIXES.get(code, ()))
                    + [str(item).strip() for item in suffix_values if str(item).strip()]
                )
            )
            full_names = tuple(
                str(item).strip() for item in full_values if str(item).strip()
            )
            self._suffixes_by_language[code] = suffixes
            self._full_names_by_language[code] = full_names

        self._all_suffixes = tuple(
            dict.fromkeys(
                suffix
                for suffixes in self._suffixes_by_language.values()
                for suffix in suffixes
            )
        )
        self._all_full_names = tuple(
            dict.fromkeys(
                name
                for names in self._full_names_by_language.values()
                for name in names
            )
        )
        self._compiled_suffix_patterns: dict[str | None, re.Pattern[str]] = {}

    def suffixes_for_language(self, language_code: str | None) -> tuple[str, ...]:
        code = (language_code or "").strip().lower()
        if code in self._suffixes_by_language:
            return tuple(
                dict.fromkeys(
                    list(self._suffixes_by_language[code])
                    + list(self._suffixes_by_language["global"])
                )
            )
        return self._all_suffixes

    def full_names_for_language(self, language_code: str | None) -> tuple[str, ...]:
        code = (language_code or "").strip().lower()
        if code in self._full_names_by_language:
            return tuple(
                dict.fromkeys(
                    list(self._full_names_by_language[code])
                    + list(self._full_names_by_language["global"])
                )
            )
        return self._all_full_names

    def forms_for_language(self, language_code: str | None) -> tuple[str, ...]:
        return self.suffixes_for_language(language_code)

    def suffix_group_for_language(self, language_code: str | None) -> str:
        suffixes = self.suffixes_for_language(language_code)
        escaped = sorted({re.escape(suffix) for suffix in suffixes}, key=len, reverse=True)
        return "|".join(escaped)

    def suffix_pattern_for_language(self, language_code: str | None) -> re.Pattern[str]:
        cache_key = (language_code or "").strip().lower() or None
        cached = self._compiled_suffix_patterns.get(cache_key)
        if cached is not None:
            return cached
        suffix_group = self.suffix_group_for_language(language_code)
        pattern = re.compile(
            rf"(?<![{_WORD_CHAR}])(?:{suffix_group}){_NOT_AFTER_SUFFIX}",
            re.UNICODE,
        )
        self._compiled_suffix_patterns[cache_key] = pattern
        return pattern

    def resolve_legal_form(self, matched_suffix: str, language_code: str | None) -> str:
        normalized = matched_suffix.casefold()
        for form in self.suffixes_for_language(language_code):
            if form.casefold() == normalized:
                return form
        return matched_suffix

    def lookup_full_name_for_suffix(
        self, matched_suffix: str, language_code: str | None
    ) -> str | None:
        normalized_suffix = matched_suffix.casefold()
        for full_name in self.full_names_for_language(language_code):
            if normalized_suffix in full_name.casefold():
                return full_name
        return None

    def company_pattern_for_language(self, language_code: str | None) -> re.Pattern[str]:
        return self.suffix_pattern_for_language(language_code)


__all__ = ["LegalFormGazetteer"]
