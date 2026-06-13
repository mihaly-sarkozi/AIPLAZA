#!/usr/bin/env python3
"""Entity gazetteer adatfájlok letöltése / generálása kb_discovery-hez."""
from __future__ import annotations

import csv
import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = ROOT / "backend" / "apps" / "kb" / "kb_discovery" / "data"

NICKNAMES_URL = (
    "https://raw.githubusercontent.com/carltonnorthern/nicknames/master/names.csv"
)
GLEIF_ELF_CSV_URL = (
    "https://www.gleif.org/lei-data/code-lists/"
    "iso-20275-entity-legal-forms-code-list/2026-02-19-elf-code-list-v1.6.csv"
)
HUN_FIRSTNAMES_URL = (
    "https://raw.githubusercontent.com/k-monitor/parldata/master/"
    "src/elasticsearch/config/keyword_marker_lists/hun_firstnames.txt"
)
HU_NAMEDAYS_URL = (
    "https://raw.githubusercontent.com/harkalygergo/hu_namedays/master/"
    "hu-HU_magyar-nevnapok-abc-sorrendben.csv"
)
ES_GIVEN_NAMES_URL = (
    "https://raw.githubusercontent.com/Rigonz/60k-Spanish-Given-Names/master/"
    "03%20Names%20R3.csv"
)
ES_MALE_NAMES_URL = (
    "https://raw.githubusercontent.com/jvalhondo/spanish-names-surnames/master/"
    "male_names.csv"
)
ES_FEMALE_NAMES_URL = (
    "https://raw.githubusercontent.com/jvalhondo/spanish-names-surnames/master/"
    "female_names.csv"
)
EN_BABY_NAMES_URL = (
    "https://raw.githubusercontent.com/hadley/data-baby-names/master/baby-names.csv"
)
WIKI_ES_HYPO_URL = (
    "https://es.wikipedia.org/wiki/Anexo:Hipocor%C3%ADsticos_en_espa%C3%B1ol?action=raw"
)
WIKI_HU_NICKNAME_URL = (
    "https://hu.wikipedia.org/wiki/Magyar_keresztnevek_bec%C3%A9z%C3%A9se?action=raw"
)
HUNGAROPEDIA_NICKNAME_URL = (
    "https://hungaropedia.org/index.php?title=Magyar_keresztnevek_bec%C3%A9z%C3%A9se&action=raw"
)

_WIKI_LINK = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")
_GLEIF_COUNTRY_TO_LANG = {
    "HU": "hu",
    "GB": "en",
    "UK": "en",
    "US": "en",
    "IE": "en",
    "AU": "en",
    "NZ": "en",
    "CA": "en",
    "ES": "es",
    "MX": "es",
    "AR": "es",
}


def _download_text(url: str, *, timeout: int = 60) -> str | None:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "AIPLAZA-gazetteer-build/1.0 (+https://github.com/)"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read().decode("utf-8", errors="replace")
    except OSError as exc:
        print(f"WARN: download failed ({url}): {exc}", file=sys.stderr)
        return None


def _download_file(url: str, target: Path, *, timeout: int = 60) -> bool:
    raw = _download_text(url, timeout=timeout)
    if raw is None:
        return False
    target.write_text(raw, encoding="utf-8")
    return True


def _ensure_dirs() -> None:
    for sub in (
        "dictionaries",
        "dictionaries/tenants",
        "dictionaries/knowledge_bases",
        "systems",
        "systems/tenants",
        "systems/knowledge_bases",
        "legal_forms",
        "person_aliases",
        "persons",
        "persons/tenants",
        "persons/knowledge_bases",
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
    if _download_gleif_legal_forms():
        return
    print("WARN: GLEIF download failed; using fallback legal forms", file=sys.stderr)
    _build_fallback_legal_forms()


def _download_gleif_legal_forms() -> bool:
    raw = _download_text(GLEIF_ELF_CSV_URL, timeout=120)
    if not raw:
        return False

    archive = DATA_ROOT / "legal_forms" / "gleif_elf_v1.6.csv"
    archive.write_text(raw, encoding="utf-8")

    forms_by_lang: dict[str, set[str]] = {key: set() for key in ("hu", "en", "es", "global")}
    reader = csv.DictReader(raw.splitlines())
    for row in reader:
        if (row.get("ELF Status ACTV/INAC") or "").strip().upper() != "ACTV":
            continue
        country = (row.get("Country Code (ISO 3166-1)") or "").strip().upper()
        bucket = _GLEIF_COUNTRY_TO_LANG.get(country, "global")
        for field in (
            "Abbreviations Local language",
            "Abbreviations transliterated",
            "Entity Legal Form name Local name",
        ):
            for token in _split_gleif_tokens(row.get(field) or ""):
                if _is_usable_legal_form(token):
                    forms_by_lang[bucket].add(token)
                    if bucket != "global":
                        forms_by_lang["global"].update(_common_global_forms(token))

    for key, values in forms_by_lang.items():
        merged = sorted(values, key=lambda item: (-len(item), item.casefold()))
        _write_json(DATA_ROOT / "legal_forms" / f"legal_forms_{key}.json", merged)
    print(
        "OK: GLEIF legal forms -> "
        f"hu={len(forms_by_lang['hu'])}, en={len(forms_by_lang['en'])}, "
        f"es={len(forms_by_lang['es'])}, global={len(forms_by_lang['global'])}"
    )
    return True


def _split_gleif_tokens(value: str) -> list[str]:
    tokens: list[str] = []
    for chunk in value.replace("\n", " ").split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        for piece in chunk.split(";"):
            piece = piece.strip()
            if piece:
                tokens.append(piece)
    return tokens


def _is_usable_legal_form(value: str) -> bool:
    cleaned = value.strip()
    if len(cleaned) < 2 or len(cleaned) > 80:
        return False
    if cleaned.isdigit():
        return False
    return any(char.isalpha() for char in cleaned)


def _common_global_forms(value: str) -> set[str]:
    upper = value.upper()
    known = {
        "GMBH",
        "AG",
        "BV",
        "NV",
        "LLC",
        "LTD",
        "PLC",
        "LLP",
        "INC",
        "CORP",
        "SA",
        "SL",
        "SRL",
        "SPA",
        "PTY LTD",
        "PTE LTD",
    }
    hits = {value for marker in known if marker in upper.replace(".", "")}
    return hits


def _build_fallback_legal_forms() -> None:
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
        ("István", "Isti", "hu"),
        ("László", "Laci", "hu"),
        ("László", "Lacika", "hu"),
        ("Gábor", "Gabi", "hu"),
        ("József", "Jóska", "hu"),
        ("József", "Józsi", "hu"),
        ("József", "Joci", "hu"),
        ("Ferenc", "Feri", "hu"),
        ("Zoltán", "Zoli", "hu"),
        ("Attila", "Ati", "hu"),
        ("Attila", "Atti", "hu"),
        ("Katalin", "Kati", "hu"),
        ("Katalin", "Kató", "hu"),
        ("Erzsébet", "Erzsi", "hu"),
        ("Erzsébet", "Böske", "hu"),
        ("Péter", "Peti", "hu"),
        ("Péter", "Petya", "hu"),
        ("András", "Bandi", "hu"),
        ("András", "Endre", "hu"),
        ("György", "Gyuri", "hu"),
        ("János", "Jani", "hu"),
        ("János", "Jancsi", "hu"),
        ("Imre", "Imi", "hu"),
        ("Tamás", "Tomi", "hu"),
        ("Balázs", "Bazsi", "hu"),
        ("Csaba", "Csabi", "hu"),
        ("Károly", "Karcsi", "hu"),
        ("Sándor", "Sanyi", "hu"),
        ("Sándor", "Sancsi", "hu"),
        ("Mária", "Mari", "hu"),
        ("Mária", "Marika", "hu"),
        ("Anna", "Ani", "hu"),
        ("Anna", "Ancsa", "hu"),
        ("Julianna", "Julcsi", "hu"),
        ("Eszter", "Eszti", "hu"),
        ("Ágnes", "Ági", "hu"),
        ("Gabriella", "Gabi", "hu"),
        ("Veronika", "Vera", "hu"),
        ("Veronika", "Roni", "hu"),
        ("Ilona", "Ili", "hu"),
        ("Ilona", "Ilus", "hu"),
        ("Sarolta", "Sári", "hu"),
        ("Edit", "Edi", "hu"),
        ("Tibor", "Tibi", "hu"),
        ("Lajos", "Lali", "hu"),
        ("Vilmos", "Vili", "hu"),
        ("Richárd", "Ricsi", "hu"),
        ("Viktor", "Viki", "hu"),
        ("Máté", "Matyi", "hu"),
        ("Dániel", "Dani", "hu"),
        ("Norbert", "Norbi", "hu"),
        ("Roland", "Roli", "hu"),
        ("Kristóf", "Krityó", "hu"),
        ("Barnabás", "Barni", "hu"),
        ("Levente", "Levi", "hu"),
        ("Botond", "Boti", "hu"),
        ("Márk", "Markó", "hu"),
        ("Ádám", "Ádi", "hu"),
        ("Gergely", "Greg", "hu"),
        ("Renáta", "Reni", "hu"),
        ("Zsuzsanna", "Zsuzsi", "hu"),
        ("Anikó", "Ani", "hu"),
        ("Ildikó", "Ildi", "hu"),
        ("Hajnalka", "Hajni", "hu"),
        ("Judit", "Jutka", "hu"),
        ("Nóra", "Nóri", "hu"),
        ("Timea", "Timi", "hu"),
        ("Orsolya", "Orsi", "hu"),
        ("Boglárka", "Bogi", "hu"),
        ("Enikő", "Eni", "hu"),
        ("Beáta", "Bea", "hu"),
        ("Teréz", "Teri", "hu"),
        ("Rozália", "Rózi", "hu"),
        ("Sárközi", "Sarkozi", "hu"),
        ("Sárközi", "Sarkozy", "hu"),
        ("Nagy", "Nagy", "hu"),
        ("Kovács", "Kovacs", "hu"),
        ("Szabó", "Szabo", "hu"),
        ("Tóth", "Toth", "hu"),
        ("Horváth", "Horvath", "hu"),
        ("Varga", "Varga", "hu"),
    ]
    es_rows = [
        ("Francisco", "Paco", "es"),
        ("Francisco", "Pancho", "es"),
        ("Francisco", "Curro", "es"),
        ("Francisco", "Fran", "es"),
        ("José", "Pepe", "es"),
        ("José", "Chepe", "es"),
        ("José", "Pepito", "es"),
        ("Antonio", "Toño", "es"),
        ("Antonio", "Toni", "es"),
        ("Antonio", "Anto", "es"),
        ("Juan", "Juanito", "es"),
        ("Juan", "Juancito", "es"),
        ("María", "Mari", "es"),
        ("María", "Marita", "es"),
        ("María", "Mariquita", "es"),
        ("Carmen", "Menchu", "es"),
        ("Concepción", "Concha", "es"),
        ("Concepción", "Conchita", "es"),
        ("Guadalupe", "Lupe", "es"),
        ("Guadalupe", "Lupita", "es"),
        ("Roberto", "Beto", "es"),
        ("Roberto", "Berto", "es"),
        ("Alberto", "Beto", "es"),
        ("Alberto", "Berto", "es"),
        ("Eduardo", "Lalo", "es"),
        ("Eduardo", "Edu", "es"),
        ("Ricardo", "Richi", "es"),
        ("Ricardo", "Riqui", "es"),
        ("Fernando", "Fer", "es"),
        ("Fernando", "Nando", "es"),
        ("Alejandro", "Alex", "es"),
        ("Alejandro", "Ale", "es"),
        ("Alejandro", "Jandro", "es"),
        ("Rafael", "Rafa", "es"),
        ("Manuel", "Manolo", "es"),
        ("Manuel", "Manu", "es"),
        ("Manuel", "Lolo", "es"),
        ("Enrique", "Quique", "es"),
        ("Enrique", "Kike", "es"),
        ("Ignacio", "Nacho", "es"),
        ("Jesús", "Chuy", "es"),
        ("Jesús", "Chus", "es"),
        ("Guillermo", "Memo", "es"),
        ("Guillermo", "Guille", "es"),
        ("Salvador", "Chava", "es"),
        ("Salvador", "Chavita", "es"),
        ("Alfonso", "Poncho", "es"),
        ("Beatriz", "Bea", "es"),
        ("Beatriz", "Beti", "es"),
        ("Isabel", "Isa", "es"),
        ("Isabel", "Chabela", "es"),
        ("Dolores", "Lola", "es"),
        ("Dolores", "Loli", "es"),
        ("Mercedes", "Merce", "es"),
        ("Mercedes", "Merche", "es"),
        ("Rosario", "Charo", "es"),
        ("Pilar", "Pili", "es"),
        ("Esperanza", "Espe", "es"),
        ("Remedios", "Reme", "es"),
        ("Inmaculada", "Inma", "es"),
        ("Ascensión", "Ascen", "es"),
        ("García", "Garcia", "es"),
        ("González", "Gonzalez", "es"),
        ("Rodríguez", "Rodriguez", "es"),
        ("Fernández", "Fernandez", "es"),
        ("López", "Lopez", "es"),
        ("Martínez", "Martinez", "es"),
        ("Sánchez", "Sanchez", "es"),
        ("Pérez", "Perez", "es"),
    ]
    for path, rows in (
        (DATA_ROOT / "person_aliases" / "person_aliases_hu.csv", hu_rows),
        (DATA_ROOT / "person_aliases" / "person_aliases_es.csv", es_rows),
    ):
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["canonical_name", "alias", "language"])
            writer.writerows(rows)

    _download_hu_aliases_into_csv(DATA_ROOT / "person_aliases" / "person_aliases_hu.csv")
    _download_es_aliases_into_csv(DATA_ROOT / "person_aliases" / "person_aliases_es.csv")


def _clean_wiki_name(raw: str) -> str:
    value = raw.strip()
    if "|" in value:
        value = value.split("|")[-1].strip()
    return value.split("(")[0].strip()


def _canonical_from_hu_alias_body(body: str) -> str:
    links = _WIKI_LINK.findall(body)
    if links:
        return _clean_wiki_name(links[-1][1] or links[-1][0])
    for part in reversed([segment.strip() for segment in body.split(",")]):
        candidate = re.sub(r"[-~].*", "", part).strip()
        candidate = candidate.replace("[[", "").replace("]]", "")
        candidate = _clean_wiki_name(candidate)
        if candidate and candidate[0].isupper():
            return candidate
    return ""


def _add_hu_alias_row(
    rows: set[tuple[str, str, str]],
    canonical: str,
    alias: str,
) -> None:
    canonical = canonical.strip()
    if not canonical or len(canonical) > 60:
        return
    for part in re.split(r"~", alias):
        value = part.strip(" .'\"")
        if len(value) < 2 or len(value) > 40:
            continue
        if value.casefold() == canonical.casefold():
            continue
        if not value[0].isupper():
            continue
        rows.add((canonical, value, "hu"))


def _parse_hu_alias_pairs(raw: str) -> set[tuple[str, str, str]]:
    rows: set[tuple[str, str, str]] = set()
    for match in re.finditer(r"''([^']+)''\s*\(([^)]+)\)", raw):
        canonical = _canonical_from_hu_alias_body(match.group(2))
        _add_hu_alias_row(rows, canonical, match.group(1).strip())

    for match in _WIKI_LINK.finditer(raw):
        canonical = _clean_wiki_name(match.group(2) or match.group(1))
        tail = raw[match.end() : match.end() + 120]
        lowered = tail.lower()
        if "általában" in lowered:
            tail = tail.split("általában", 1)[1]
        elif ":" in tail[:40]:
            tail = tail.split(":", 1)[1]
        else:
            continue
        tail = tail.split(".", 1)[0]
        for part in re.split(r",|\svagy\s", tail):
            part = part.strip(" '\"")
            if part and part[0].isupper() and " " not in part:
                _add_hu_alias_row(rows, canonical, part)
    return rows


def _download_hu_aliases_into_csv(target: Path) -> None:
    merged_rows: set[tuple[str, str, str]] = set()
    if target.is_file():
        with target.open(encoding="utf-8", newline="") as handle:
            merged_rows.update(tuple(row.values()) for row in csv.DictReader(handle))

    downloaded = 0
    for url in (WIKI_HU_NICKNAME_URL, HUNGAROPEDIA_NICKNAME_URL):
        raw = _download_text(url, timeout=60)
        if not raw:
            continue
        pairs = _parse_hu_alias_pairs(raw)
        before = len(merged_rows)
        merged_rows.update(pairs)
        downloaded += len(merged_rows) - before

    if downloaded == 0 and not merged_rows:
        return

    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["canonical_name", "alias", "language"])
        writer.writerows(sorted(merged_rows))
    print(f"OK: {len(merged_rows)} hungarian aliases -> {target.relative_to(ROOT)}")


def _download_es_aliases_into_csv(target: Path) -> None:
    raw = _download_text(WIKI_ES_HYPO_URL, timeout=60)
    if not raw:
        return

    rows: list[tuple[str, str, str]] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line.startswith("*"):
            continue
        body = line.lstrip("*").strip()
        if ":" not in body:
            continue
        canonical_raw, aliases_raw = body.split(":", 1)
        canonical = canonical_raw.replace("[[", "").replace("]]", "").strip()
        aliases_raw = aliases_raw.replace("''", "")
        if not canonical or len(canonical) > 60:
            continue
        for alias in aliases_raw.split(","):
            alias = alias.strip().strip(".")
            if not alias or alias.casefold() == canonical.casefold() or len(alias) > 40:
                continue
            rows.append((canonical, alias, "es"))

    if not rows:
        return

    existing: set[tuple[str, str, str]] = set()
    if target.is_file():
        with target.open(encoding="utf-8", newline="") as handle:
            existing.update(tuple(row.values()) for row in csv.DictReader(handle))

    merged = sorted(existing | set(rows))
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["canonical_name", "alias", "language"])
        writer.writerows(merged)
    print(f"OK: {len(merged)} spanish aliases -> {target.relative_to(ROOT)}")


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
    generated = _download_given_names_from_sources()
    if generated:
        return

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
                top = dataset.get_top_names(n=2000, gender=gender, country=country)
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


def _download_given_names_from_sources() -> bool:
    hu_names = _load_hu_given_names()
    es_names = _load_es_given_names()
    en_names = _load_en_given_names()
    if not any((hu_names, es_names, en_names)):
        return False

    for code, names in (("hu", hu_names), ("en", en_names), ("es", es_names)):
        if not names:
            continue
        path = DATA_ROOT / "names" / f"given_names_{code}.txt"
        path.write_text("\n".join(sorted(names)) + "\n", encoding="utf-8")
        print(f"OK: {len(names)} given names -> {path.relative_to(ROOT)}")
    return True


def _load_hu_given_names() -> set[str]:
    names: set[str] = set()
    raw = _download_text(HUN_FIRSTNAMES_URL)
    if raw:
        for line in raw.splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                names.add(line)
    raw = _download_text(HU_NAMEDAYS_URL)
    if raw:
        reader = csv.reader(raw.splitlines())
        for row in reader:
            if row:
                names.add(str(row[0]).strip())
    names.update(_names_from_dataset("Hungary"))
    return {name for name in names if len(name) >= 2}


def _load_es_given_names() -> set[str]:
    names: set[str] = set()
    raw = _download_text(ES_GIVEN_NAMES_URL)
    if raw:
        reader = csv.reader(raw.splitlines())
        next(reader, None)
        for row in reader:
            if row:
                first = str(row[0]).strip().split()[0]
                if first:
                    names.add(first.title())
    for url in (ES_MALE_NAMES_URL, ES_FEMALE_NAMES_URL):
        raw = _download_text(url)
        if not raw:
            continue
        reader = csv.reader(raw.splitlines())
        next(reader, None)
        for row in reader:
            if not row:
                continue
            first = str(row[0]).strip().split()[0]
            if first:
                names.add(first.title())
    names.update(_names_from_dataset("Spain"))
    return {name for name in names if len(name) >= 2}


def _load_en_given_names() -> set[str]:
    names: set[str] = set()
    raw = _download_text(EN_BABY_NAMES_URL)
    if raw:
        reader = csv.reader(raw.splitlines())
        next(reader, None)
        counts: dict[str, float] = {}
        for row in reader:
            if len(row) < 3:
                continue
            name = str(row[1]).strip().title()
            try:
                weight = float(row[2])
            except ValueError:
                continue
            counts[name] = counts.get(name, 0.0) + weight
        for name, _weight in sorted(counts.items(), key=lambda item: item[1], reverse=True)[:2500]:
            names.add(name)
    names.update(_names_from_dataset("United Kingdom"))
    return {name for name in names if len(name) >= 2}


def _names_from_dataset(country: str) -> set[str]:
    try:
        from names_dataset import NameDataset  # type: ignore
    except ImportError:
        return set()
    dataset = NameDataset()
    collected: set[str] = set()
    for gender in ("M", "F"):
        try:
            top = dataset.get_top_names(n=2000, gender=gender, country=country)
        except Exception:
            continue
        for item in top or []:
            if isinstance(item, (list, tuple)) and item:
                collected.add(str(item[0]).strip())
            elif isinstance(item, str):
                collected.add(item.strip())
    return collected


def _build_example_tenant_kb_files() -> None:
    _write_json(
        DATA_ROOT / "dictionaries" / "tenants" / "demo.json",
        [
            {
                "name": "Zalka 2000",
                "type": "company",
                "confidence": 0.9,
                "aliases": ["Zalka2000"],
            },
            {
                "name": "Belső CRM",
                "type": "system",
                "confidence": 0.85,
            },
        ],
    )
    _write_json(
        DATA_ROOT / "dictionaries" / "knowledge_bases" / "example-kb.json",
        [
            {
                "name": "Projekt Atlas",
                "type": "product",
                "confidence": 0.88,
            },
            {
                "name": "Tanítási modul",
                "type": "product",
                "confidence": 0.82,
                "aliases": ["Training modul"],
            },
        ],
    )
    _write_json(
        DATA_ROOT / "systems" / "tenants" / "demo.json",
        {
            "systems": ["Belső CRM", "Monday.com", "Google Drive"],
        },
    )
    _write_json(
        DATA_ROOT / "systems" / "knowledge_bases" / "example-kb.json",
        {
            "systems": ["Projekt Atlas API", "ElasticSearch"],
        },
    )


def _build_example_person_files() -> None:
    _write_json(
        DATA_ROOT / "persons" / "tenants" / "demo.json",
        [
            {
                "name": "Mihály Sárközi",
                "aliases": ["Mihály", "Misi", "Sarkozi", "Sárközi"],
            }
        ],
    )
    _write_json(
        DATA_ROOT / "persons" / "knowledge_bases" / "example-kb.json",
        [
            {
                "name": "Carlos García",
                "aliases": ["Carlos", "Garcia", "García"],
            }
        ],
    )


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
    _build_example_tenant_kb_files()
    _build_example_person_files()
    _download_en_nicknames()
    _export_given_names()
    print(f"Entity gazetteer data ready under {DATA_ROOT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
