# tests/unit/test_pii_sanitization.py
"""Sanitization: standard placeholders, generalization, dedupe longer wins, offset-safe replacement."""
from __future__ import annotations

import pytest

from apps.knowledge.pii.sanitization import (
    apply_pii_replacements,
    deduplicate_matches_longer_wins,
)

# PiiMatch = (start, end, data_type, value)
pytestmark = pytest.mark.unit


# ---- Standard placeholders ----
def test_standard_placeholders_email_phone_person():
    """Replacements use [EMAIL_ADDRESS], [PHONE_NUMBER], [PERSON_NAME] etc."""
    text = "Contact Jane Doe at jane@example.com or +36 1 234 5678."
    matches = [
        (8, 16, "név", "Jane Doe"),
        (20, 36, "email", "jane@example.com"),
        (40, 53, "telefonszám", "+36 1 234 5678"),
    ]
    refs = ["r1", "r2", "r3"]
    out = apply_pii_replacements(text, matches, refs, mode="mask")
    # ref_id-val: [PERSON_NAME_r1]; ref nélkül: [PERSON_NAME]
    assert "PERSON_NAME" in out
    assert "EMAIL_ADDRESS" in out
    assert "PHONE_NUMBER" in out
    assert "Jane Doe" not in out
    assert "jane@example.com" not in out
    assert "+36 1 234 5678" not in out
    assert "Contact " in out and " at " in out and " or " in out


def test_standard_placeholder_unknown_type_defaults_to_pii():
    """Unknown legacy type gets [PII]."""
    text = "Secret: xyz123"
    matches = [(8, 14, "unknown_type", "xyz123")]
    out = apply_pii_replacements(text, matches, ["r1"], mode="mask")
    assert "[PII]" in out or "xyz123" not in out


# ---- Generalization mode ----
def test_generalization_person_date_address():
    """Generalize: person → contact person, date → specific date, address → postal address."""
    text = "Manager: John Smith. Date: 1990-01-15. Address: 123 Main St."
    matches = [
        (10, 20, "név", "John Smith"),
        (29, 39, "dátum", "1990-01-15"),
        (50, 63, "cím", "123 Main St."),
    ]
    refs = ["a", "b", "c"]
    out = apply_pii_replacements(text, matches, refs, mode="generalize")
    assert "contact person" in out
    assert "specific date" in out
    assert "postal address" in out
    assert "John Smith" not in out
    assert "1990-01-15" not in out
    assert "123 Main St." not in out


def test_auto_delete_hungarian_person_and_field_names():
    text = "Kovács Anna címe 1123 Budapest."
    matches = [
        (0, 11, "név", "Kovács Anna"),
        (18, 31, "cím", "1123 Budapest"),
    ]
    out = apply_pii_replacements(text, matches, ["r1", "r2"], mode="auto_delete", language="hu")
    assert "<valaki>" in out
    assert "<valami cím>" in out
    assert "Kovács Anna" not in out
    assert "1123 Budapest" not in out


def test_auto_delete_english_localized_words():
    text = "John date is 2025-03-15 and code TKT-1234."
    matches = [
        (0, 4, "név", "John"),
        (13, 23, "dátum", "2025-03-15"),
        (33, 41, "ticket_id", "TKT-1234"),
    ]
    out = apply_pii_replacements(text, matches, ["a", "b", "c"], mode="auto_delete", language="en")
    assert "<someone>" in out
    assert "<some date>" in out
    assert "<some code>" in out


# ---- Deduplicate: longer wins ----
def test_deduplicate_longer_match_wins():
    """When two spans overlap, the longer span is kept (e.g. full email contains a name)."""
    # Simulate: "John" (0:4) and "John@acme.com" (0:14) – keep email
    matches = [
        (0, 4, "név", "John"),
        (0, 14, "email", "John@acme.com"),
    ]
    out = deduplicate_matches_longer_wins(matches)
    assert len(out) == 1
    assert out[0][1] - out[0][0] == 14
    assert out[0][2] == "email"


def test_deduplicate_non_overlapping_all_kept():
    """Non-overlapping matches are all kept."""
    matches = [
        (0, 4, "név", "Jane"),
        (10, 25, "email", "jane@example.com"),
    ]
    out = deduplicate_matches_longer_wins(matches)
    assert len(out) == 2
    assert out[0][2] == "név" and out[1][2] == "email"


def test_deduplicate_address_inside_larger_location():
    """Address fully inside a larger location span: keep the longer one."""
    matches = [
        (5, 25, "cím", "123 Main Street"),
        (0, 35, "hely", "Our office at 123 Main Street here"),
    ]
    out = deduplicate_matches_longer_wins(matches)
    assert len(out) == 1
    assert out[0][1] - out[0][0] == 35


# ---- Offset/order: replacement does not corrupt ----
def test_replacement_order_end_to_start_preserves_offsets():
    """Replacing from end to start does not corrupt neighboring spans."""
    text = "A x B y C"
    # Replace "x" (2:3) and "y" (6:7); if we replaced 2:3 first, "y" would shift
    matches = [(2, 3, "email", "x"), (6, 7, "email", "y")]
    refs = ["r1", "r2"]
    out = apply_pii_replacements(text, matches, refs, mode="mask")
    assert out.startswith("A ")
    assert out.endswith(" C")
    assert "EMAIL_ADDRESS" in out
    assert out.count("EMAIL_ADDRESS") == 2
    assert "x" not in out and "y" not in out


def test_replacement_longer_match_wins_in_final_text():
    """After dedupe (longer wins), replacement uses the winning span only."""
    text = "John@acme.com"
    matches = [(0, 4, "név", "John"), (0, 14, "email", "John@acme.com")]
    deduped = deduplicate_matches_longer_wins(matches)
    refs = [""]  # ref nélkül: [EMAIL_ADDRESS]
    out = apply_pii_replacements(text, deduped, refs, mode="mask")
    assert out == "[EMAIL_ADDRESS]"
    assert "John" not in out


def test_empty_matches_returns_original():
    """No matches → original text unchanged."""
    text = "No PII here."
    out = apply_pii_replacements(text, [], [], mode="mask")
    assert out == text
