from __future__ import annotations

import pytest

from apps.kb.kb_discovery.gazetteers.loaders import (
    load_name_lines,
    normalize_given_name_line,
)

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("Aba", "Aba"),
        ('Aba;"1112"', "Aba"),
        ("Abelárd", "Abelárd"),
        ('Abelárd;"0421"', "Abelárd"),
        ("  Anna-Mária  ", "Anna-Mária"),
        ("# comment", None),
        ("01", None),
        ('01;"0710', None),
        ('03;"0630"', None),
        ("08z", None),
        ('08z;"0803', None),
        ("", None),
        ("A1bert", None),
    ],
)
def test_normalize_given_name_line(line: str, expected: str | None) -> None:
    assert normalize_given_name_line(line) == expected


def test_load_name_lines_filters_nameday_metadata(tmp_path) -> None:
    path = tmp_path / "given_names_hu.txt"
    path.write_text(
        "\n".join(
            [
                '01;"0710',
                "Aba",
                'Aba;"1112"',
                "Mihály",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    names = load_name_lines(path)
    assert names == frozenset({"Aba", "Mihály"})


def test_legal_form_gazetteer_caches_compiled_patterns() -> None:
    from apps.kb.kb_discovery.gazetteers.LegalFormGazetteer import LegalFormGazetteer

    gazetteer = LegalFormGazetteer()
    first = gazetteer.suffix_pattern_for_language("hu")
    second = gazetteer.suffix_pattern_for_language("hu")
    assert first is second

    other = gazetteer.suffix_pattern_for_language("en")
    assert other is not first


def test_given_name_gazetteer_uses_static_files_only() -> None:
    from apps.kb.kb_discovery.gazetteers.GivenNameGazetteer import GivenNameGazetteer

    gazetteer = GivenNameGazetteer()
    hu_names = gazetteer.names_for("hu")
    assert "Mihály" in hu_names
    assert "01" not in hu_names
    assert 'Aba;"1112"' not in hu_names
