from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


def load_json(path: Path, default: Any) -> Any:
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def load_alias_rows(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    rows: list[dict[str, str]] = []
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            canonical = str(row.get("canonical_name") or "").strip()
            alias = str(row.get("alias") or "").strip()
            language = str(row.get("language") or "").strip().lower()
            if canonical and alias:
                rows.append(
                    {
                        "canonical_name": canonical,
                        "alias": alias,
                        "language": language,
                    }
                )
    return rows


def load_name_lines(path: Path) -> frozenset[str]:
    if not path.is_file():
        return frozenset()
    names = {line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()}
    return frozenset(names)


__all__ = ["load_alias_rows", "load_json", "load_name_lines"]
