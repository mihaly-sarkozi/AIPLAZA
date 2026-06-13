from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from apps.kb.kb_discovery.gazetteers.data_paths import data_file
from apps.kb.kb_discovery.gazetteers.loaders import load_name_lines

if TYPE_CHECKING:
    from names_dataset import NameDataset

logger = logging.getLogger(__name__)

_COUNTRY_BY_CODE = {
    "hu": "Hungary",
    "en": "United Kingdom",
    "es": "Spain",
}

_DATASET: NameDataset | None = None
_DATASET_UNAVAILABLE = False


def _shared_name_dataset() -> NameDataset | None:
    global _DATASET, _DATASET_UNAVAILABLE
    if _DATASET_UNAVAILABLE:
        return None
    if _DATASET is not None:
        return _DATASET
    try:
        from names_dataset import NameDataset
    except ImportError:
        logger.debug("names-dataset not available for GivenNameGazetteer")
        _DATASET_UNAVAILABLE = True
        return None
    try:
        _DATASET = NameDataset()
    except Exception:
        logger.warning("names-dataset initialization failed", exc_info=True)
        _DATASET_UNAVAILABLE = True
        return None
    return _DATASET


class GivenNameGazetteer:
    def __init__(self) -> None:
        self._file_names = {
            "hu": load_name_lines(data_file("names", "given_names_hu.txt")),
            "en": load_name_lines(data_file("names", "given_names_en.txt")),
            "es": load_name_lines(data_file("names", "given_names_es.txt")),
        }
        self._runtime_cache: dict[str, frozenset[str]] = {}

    def names_for(self, language_code: str | None) -> frozenset[str]:
        code = (language_code or "").strip().lower()
        if code not in _COUNTRY_BY_CODE:
            return self._all_names()
        if code not in self._runtime_cache:
            self._runtime_cache[code] = self._load_for_code(code)
        return self._runtime_cache[code]

    def _load_for_code(self, code: str) -> frozenset[str]:
        names = set(self._file_names.get(code, frozenset()))
        names.update(self._names_from_dataset(code))
        return frozenset(name for name in names if name)

    def _names_from_dataset(self, code: str) -> set[str]:
        country = _COUNTRY_BY_CODE.get(code)
        if not country:
            return set()
        dataset = _shared_name_dataset()
        if dataset is None:
            return set()

        collected: set[str] = set()
        for gender in ("M", "F"):
            try:
                top = dataset.get_top_names(n=400, gender=gender, country=country)
            except Exception:
                logger.debug("names-dataset lookup failed (%s/%s)", country, gender, exc_info=True)
                continue
            for item in top or []:
                if isinstance(item, (list, tuple)) and item:
                    collected.add(str(item[0]).strip())
                elif isinstance(item, str):
                    collected.add(item.strip())
        return {name for name in collected if len(name) >= 2}

    def _all_names(self) -> frozenset[str]:
        combined: set[str] = set()
        for code in _COUNTRY_BY_CODE:
            combined.update(self.names_for(code))
        return frozenset(combined)


__all__ = ["GivenNameGazetteer"]
