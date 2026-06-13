#!/usr/bin/env python3
"""Entity gazetteer adatfájlok letöltése / generálása kb_discovery-hez."""
from __future__ import annotations

import csv
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = ROOT / "backend" / "apps" / "kb" / "kb_discovery" / "data"

NICKNAMES_URL = (
    "https://raw.githubusercontent.com/carltonnorthern/nicknames/master/names.csv"
)


def _ensure_dirs() -> None:
    for sub in (
        "dictionaries",
        "dictionaries/tenants",
        "dictionaries/knowledge_bases",
        "systems",
        "legal_forms",
        "person_aliases",
        "names",
    ):
        (DATA_ROOT / sub).mkdir(parents=True, exist_ok=True)


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _build_default_entities() -> None:
    entries = [
        {"name": "AI Plaza", "type": "product", "confidence": 0.92},
        {"name": "AIPLAZA", "type": "product", "confidence": 0.9, "aliases": ["AI Plaza"]},
        {"name": "Zalka 2000", "type": "company", "confidence": 0.88},
        {"name": "HubSpot", "type": "system", "confidence": 0.9},
    ]
    _write_json(DATA_ROOT / "dictionaries" / "default_entities.json", entries)


def _build_default_systems() -> None:
    payload = {
        "default": [
            "HubSpot",
            "Salesforce",
            "SAP",
            "Jira",
            "Confluence",
            "Google Workspace",
            "Microsoft 365",
            "CRM",
            "Slack",
            "Notion",
        ],
        "products": ["HubSpot", "Salesforce", "SAP"],
    }
    _write_json(DATA_ROOT / "systems" / "default_systems.json", payload)


def _build_legal_forms() -> None:
    forms = {
        "hu": [
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
            "Nonprofit Kft.",
            "Egyesület",
            "Alapítvány",
        ],
        "en": [
            "Ltd",
            "Ltd.",
            "Limited",
            "LLC",
            "L.L.C.",
            "Inc.",
            "Inc",
            "Corp.",
            "Corporation",
            "PLC",
            "LLP",
            "GmbH",
            "AG",
        ],
        "es": [
            "S.L.",
            "SL",
            "S.L.U.",
            "S.A.",
            "SA",
            "Sociedad Limitada",
            "Sociedad Anónima",
            "Autónomo",
            "Asociación",
            "Fundación",
            "Cooperativa",
        ],
        "global": ["B.V.", "N.V.", "S.A.", "S.à r.l.", "Pty Ltd", "Pte. Ltd."],
    }
    for key, values in forms.items():
        _write_json(DATA_ROOT / "legal_forms" / f"legal_forms_{key}.json", values)


def _build_hu_es_aliases() -> None:
    hu_rows = [
        ("Mihály", "Misi", "hu"),
        ("Mihály", "Miska", "hu"),
        ("István", "Pisti", "hu"),
        ("István", "Pista", "hu"),
        ("László", "Laci", "hu"),
        ("László", "Lacika", "hu"),
        ("Gábor", "Gabi", "hu"),
        ("József", "Jóska", "hu"),
        ("József", "Józsi", "hu"),
        ("Ferenc", "Feri", "hu"),
        ("Zoltán", "Zoli", "hu"),
        ("Attila", "Ati", "hu"),
        ("Katalin", "Kati", "hu"),
        ("Erzsébet", "Erzsi", "hu"),
        ("Sárközi", "Sarkozi", "hu"),
    ]
    es_rows = [
        ("Francisco", "Paco", "es"),
        ("Francisco", "Pancho", "es"),
        ("José", "Pepe", "es"),
        ("Antonio", "Toño", "es"),
        ("Concepción", "Concha", "es"),
        ("Guadalupe", "Lupe", "es"),
        ("Juan", "Juanito", "es"),
        ("María", "Mari", "es"),
        ("Roberto", "Beto", "es"),
    ]
    for path, rows in (
        (DATA_ROOT / "person_aliases" / "person_aliases_hu.csv", hu_rows),
        (DATA_ROOT / "person_aliases" / "person_aliases_es.csv", es_rows),
    ):
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["canonical_name", "alias", "language"])
            writer.writerows(rows)


def _download_en_nicknames() -> None:
    target = DATA_ROOT / "person_aliases" / "person_aliases_en.csv"
    try:
        with urllib.request.urlopen(NICKNAMES_URL, timeout=30) as response:
            raw = response.read().decode("utf-8", errors="replace")
    except OSError as exc:
        print(f"WARN: nicknames download failed: {exc}", file=sys.stderr)
        _write_fallback_en_nicknames(target)
        return

    rows: list[tuple[str, str, str]] = []
    reader = csv.reader(raw.splitlines())
    header = next(reader, None)
    for row in reader:
        if len(row) < 3:
            continue
        canonical = str(row[0]).strip().title()
        nickname = str(row[2]).strip().title()
        if not canonical or not nickname:
            continue
        rows.append((canonical, nickname, "en"))
        if len(rows) >= 3000:
            break

    if not rows:
        _write_fallback_en_nicknames(target)
        return

    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["canonical_name", "alias", "language"])
        writer.writerows(rows)
    print(f"OK: {len(rows)} english nicknames -> {target.relative_to(ROOT)}")


def _write_fallback_en_nicknames(target: Path) -> None:
    rows = [
        ("William", "Bill", "en"),
        ("Robert", "Bob", "en"),
        ("Michael", "Mike", "en"),
        ("Elizabeth", "Liz", "en"),
        ("Richard", "Rick", "en"),
        ("James", "Jim", "en"),
        ("John", "Jack", "en"),
    ]
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["canonical_name", "alias", "language"])
        writer.writerows(rows)


def _export_given_names() -> None:
    try:
        from names_dataset import NameDataset  # type: ignore
    except ImportError:
        print("WARN: names-dataset not installed; skipping given name export", file=sys.stderr)
        _write_fallback_given_names()
        return

    dataset = NameDataset()
    country_map = {"hu": "Hungary", "en": "United Kingdom", "es": "Spain"}
    for code, country in country_map.items():
        names: set[str] = set()
        for gender in ("M", "F"):
            try:
                top = dataset.get_top_names(n=300, gender=gender, country=country)
            except Exception:
                continue
            for item in top or []:
                if isinstance(item, (list, tuple)) and item:
                    names.add(str(item[0]).strip())
                elif isinstance(item, str):
                    names.add(item.strip())
        if not names:
            continue
        path = DATA_ROOT / "names" / f"given_names_{code}.txt"
        path.write_text("\n".join(sorted(names)) + "\n", encoding="utf-8")
        print(f"OK: {len(names)} given names -> {path.relative_to(ROOT)}")


def _write_fallback_given_names() -> None:
    fallback = {
        "hu": ["Mihály", "István", "László", "Gábor", "József", "Ferenc", "Anna", "Katalin"],
        "en": ["John", "Michael", "William", "Robert", "James", "Mary", "Elizabeth", "Sarah"],
        "es": ["José", "Juan", "Francisco", "Antonio", "María", "Carmen", "Ana", "Laura"],
    }
    for code, names in fallback.items():
        path = DATA_ROOT / "names" / f"given_names_{code}.txt"
        path.write_text("\n".join(names) + "\n", encoding="utf-8")


def main() -> int:
    _ensure_dirs()
    _build_default_entities()
    _build_default_systems()
    _build_legal_forms()
    _build_hu_es_aliases()
    _download_en_nicknames()
    _export_given_names()
    print(f"Entity gazetteer data ready under {DATA_ROOT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
