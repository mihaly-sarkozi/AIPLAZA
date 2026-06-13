from __future__ import annotations

import re

_HU_MONTHS = {
    "január": "01", "február": "02", "március": "03", "április": "04",
    "május": "05", "június": "06", "július": "07", "augusztus": "08",
    "szeptember": "09", "október": "10", "november": "11", "december": "12",
}


class DateRecognizer:
    _NUMERIC = re.compile(r"\b(\d{4})[./-]\s?(\d{1,2})[./-]\s?(\d{1,2})\b\.?")
    _HU = re.compile(
        r"\b(\d{4})\.\s?(január|február|március|április|május|június|július|augusztus|szeptember|október|november|december)\s?(\d{1,2})(?:-től|-ig|-tól|-től)?\.?\b",
        re.IGNORECASE,
    )

    def recognize(self, chunk) -> list[dict]:
        mentions: list[dict] = []
        for match in self._NUMERIC.finditer(chunk.text):
            y, m, d = match.groups()
            mentions.append(
                {
                    "raw_text": match.group(0),
                    "normalized_start": f"{y}-{int(m):02d}-{int(d):02d}",
                    "normalized_end": None,
                    "temporal_type": "date",
                }
            )
        for match in self._HU.finditer(chunk.text):
            y, month_name, day = match.groups()
            month = _HU_MONTHS[month_name.lower()]
            mentions.append(
                {
                    "raw_text": match.group(0),
                    "normalized_start": f"{y}-{month}-{int(day):02d}",
                    "normalized_end": None,
                    "temporal_type": "date",
                }
            )
        return mentions


class DateRangeRecognizer:
    _RANGE = re.compile(
        r"\b(\d{4})[./-](\d{1,2})[./-](\d{1,2})\s*[-–]\s*(\d{4})[./-](\d{1,2})[./-](\d{1,2})\b"
    )

    def recognize(self, chunk) -> list[dict]:
        mentions: list[dict] = []
        for match in self._RANGE.finditer(chunk.text):
            y1, m1, d1, y2, m2, d2 = match.groups()
            mentions.append(
                {
                    "raw_text": match.group(0),
                    "normalized_start": f"{y1}-{int(m1):02d}-{int(d1):02d}",
                    "normalized_end": f"{y2}-{int(m2):02d}-{int(d2):02d}",
                    "temporal_type": "date_range",
                }
            )
        return mentions


class RelativeDateResolver:
    _RELATIVE = re.compile(r"\b(ma|holnap|tegnap|jövő héten|múlt héten)\b", re.IGNORECASE)

    def recognize(self, chunk) -> list[dict]:
        return [
            {
                "raw_text": match.group(0),
                "normalized_start": None,
                "normalized_end": None,
                "temporal_type": "relative",
            }
            for match in self._RELATIVE.finditer(chunk.text)
        ]


class DeadlineRecognizer:
    _DEADLINE = re.compile(r"\b(határidő|deadline)\s*:?\s*([^.!\n]+)", re.IGNORECASE)

    def recognize(self, chunk) -> list[dict]:
        return [
            {
                "raw_text": match.group(0).strip(),
                "normalized_start": None,
                "normalized_end": None,
                "temporal_type": "deadline",
            }
            for match in self._DEADLINE.finditer(chunk.text)
        ]


class RecurrenceRecognizer:
    _RECURRENCE = re.compile(r"\b(napi|heti|havi|éves|ismétlődő)\b", re.IGNORECASE)

    def recognize(self, chunk) -> list[dict]:
        return [
            {
                "raw_text": match.group(0),
                "normalized_start": None,
                "normalized_end": None,
                "temporal_type": "recurrence",
            }
            for match in self._RECURRENCE.finditer(chunk.text)
        ]


class TemporalContextScorer:
    def score(self, mention: dict) -> float:
        if mention.get("normalized_start"):
            return 0.95
        if mention.get("temporal_type") == "deadline":
            return 0.8
        return 0.6


__all__ = [
    "DateRecognizer",
    "DateRangeRecognizer",
    "DeadlineRecognizer",
    "RecurrenceRecognizer",
    "RelativeDateResolver",
    "TemporalContextScorer",
]
