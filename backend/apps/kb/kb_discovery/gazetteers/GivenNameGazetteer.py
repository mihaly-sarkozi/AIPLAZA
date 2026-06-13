from __future__ import annotations

from apps.kb.kb_discovery.gazetteers.data_paths import data_file
from apps.kb.kb_discovery.gazetteers.loaders import load_name_lines


class GivenNameGazetteer:
    def __init__(self) -> None:
        self._file_names = {
            "hu": load_name_lines(data_file("names", "given_names_hu.txt")),
            "en": load_name_lines(data_file("names", "given_names_en.txt")),
            "es": load_name_lines(data_file("names", "given_names_es.txt")),
        }

    def names_for(self, language_code: str | None) -> frozenset[str]:
        code = (language_code or "").strip().lower()
        if code in self._file_names:
            return self._file_names[code]
        return self._all_names()

    def _all_names(self) -> frozenset[str]:
        combined: set[str] = set()
        for names in self._file_names.values():
            combined.update(names)
        return frozenset(combined)


__all__ = ["GivenNameGazetteer"]
