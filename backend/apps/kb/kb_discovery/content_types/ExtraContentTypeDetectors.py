from __future__ import annotations

import re


class NoteDetector:
    _NOTE = re.compile(r"\b(megjegyzés|note|jegyzet|remark)\b", re.IGNORECASE)

    name = "note_detector"

    def detect(self, text: str) -> tuple[str, float, tuple[str, ...]] | None:
        if self._NOTE.search(text):
            return ("note", 0.72, ("note_marker",))
        return None


class WarningDetector:
    _WARNING = re.compile(r"\b(figyelem|warning|veszély|fontos)\b", re.IGNORECASE)

    name = "warning_detector"

    def detect(self, text: str) -> tuple[str, float, tuple[str, ...]] | None:
        if self._WARNING.search(text):
            return ("warning", 0.78, ("warning_marker",))
        return None


class DefinitionDetector:
    _DEFINITION = re.compile(r"\b(jelentése|definíció|definition|az\s+\w+\s+egy)\b", re.IGNORECASE)

    name = "definition_detector"

    def detect(self, text: str) -> tuple[str, float, tuple[str, ...]] | None:
        if self._DEFINITION.search(text):
            return ("definition", 0.7, ("definition_marker",))
        return None


class ReferenceDetector:
    _REFERENCE = re.compile(r"\b(lásd|see also|referencia|reference|hivatkozás)\b", re.IGNORECASE)

    name = "reference_detector"

    def detect(self, text: str) -> tuple[str, float, tuple[str, ...]] | None:
        if self._REFERENCE.search(text):
            return ("reference", 0.68, ("reference_marker",))
        return None


__all__ = ["DefinitionDetector", "NoteDetector", "ReferenceDetector", "WarningDetector"]
