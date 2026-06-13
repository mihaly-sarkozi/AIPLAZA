from __future__ import annotations

import re

from apps.kb.kb_discovery.spatial.SpatialContextScorer import SpatialContextScorer


class LocationRecognizer:
    _PATTERN = re.compile(
        r"\b(\w+?i\s+irod\w+|\w+?i\s+telephely\w+|\w+?i\s+raktár\w+)",
        re.IGNORECASE | re.UNICODE,
    )
    _CITIES = ("budapest", "debrecen", "szeged", "győr", "pécs")

    def recognize(self, text: str) -> list[dict]:
        mentions: list[dict] = []
        for match in self._PATTERN.finditer(text):
            mentions.append(
                {
                    "raw_text": match.group(1),
                    "normalized_location": match.group(1).lower(),
                    "location_type": "office",
                }
            )
        lower = text.lower()
        for city in self._CITIES:
            if city in lower:
                mentions.append(
                    {
                        "raw_text": city,
                        "normalized_location": city,
                        "location_type": "city",
                    }
                )
        return mentions


class AddressRecognizer:
    _PATTERN = re.compile(
        r"\b(\d{4}\s[\wáéíóöőúüűÁÉÍÓÖŐÚÜŰ.-]+\s(?:utca|út|tér|körút)\s?\d+\.?)\b",
        re.IGNORECASE,
    )

    def recognize(self, text: str) -> list[dict]:
        return [
            {
                "raw_text": match.group(1),
                "normalized_location": match.group(1).lower(),
                "location_type": "address",
            }
            for match in self._PATTERN.finditer(text)
        ]


class SiteDictionaryProvider:
    def load(self, *, tenant_slug: str | None) -> list[dict]:
        return []


class RoomRecognizer:
    _PATTERN = re.compile(r"\b(tárgyaló\s[\w-]+|meeting room\s[\w-]+)\b", re.IGNORECASE)

    def recognize(self, text: str) -> list[dict]:
        return [
            {
                "raw_text": match.group(1),
                "normalized_location": match.group(1).lower(),
                "location_type": "room",
            }
            for match in self._PATTERN.finditer(text)
        ]


class RegionRecognizer:
    _REGIONS = ("dunántúl", "alföld", "transdanubia")

    def recognize(self, text: str) -> list[dict]:
        lower = text.lower()
        return [
            {"raw_text": region, "normalized_location": region, "location_type": "region"}
            for region in self._REGIONS
            if region in lower
        ]


__all__ = [
    "AddressRecognizer",
    "LocationRecognizer",
    "RegionRecognizer",
    "RoomRecognizer",
    "SiteDictionaryProvider",
]
