# tests/unit/test_address_detection.py
"""Tests for address detection: HU/EN/ES full and shortened forms, date-not-address."""
from __future__ import annotations

import pytest

from apps.knowledge.pii_gdpr.enums import EntityType
from apps.knowledge.pii_gdpr.pipeline.multilingual_analyzer import MultilingualAnalyzer
from apps.knowledge.pii_gdpr.pipeline.span_extender import find_address_blocks

pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


def _get_address_detections(text: str, language: str = "hu") -> list:
    """Return POSTAL_ADDRESS detections from the analyzer."""
    analyzer = MultilingualAnalyzer()
    results = analyzer.analyze(text, language)
    return [r for r in results if r.entity_type == EntityType.POSTAL_ADDRESS]


def _get_dob_detections(text: str, language: str = "hu") -> list:
    """Return DATE_OF_BIRTH detections."""
    analyzer = MultilingualAnalyzer()
    results = analyzer.analyze(text, language)
    return [r for r in results if r.entity_type == EntityType.DATE_OF_BIRTH]


# --- Hungarian full address ---


def test_hungarian_full_address():
    """HU: 1024 Budapest, Keleti Károly utca 18-24. A épület, 4. emelet, 2/7. ajtó"""
    text = "1024 Budapest, Keleti Károly utca 18-24. A épület, 4. emelet, 2/7. ajtó"
    addrs = _get_address_detections(text, "hu")
    assert len(addrs) >= 1, f"Expected at least one address, got: {addrs}"
    matched = addrs[0].matched_text
    assert "18-24" in matched, f"Address should include 18-24: {matched}"
    # Extension through A épület, 4. emelet, 2/7. ajtó (at least one continuation block)
    has_continuation = (
        "A épület" in matched or "4. emelet" in matched or "2/7. ajtó" in matched
    )
    assert has_continuation, (
        f"Address should extend through continuation blocks (A épület, 4. emelet, 2/7. ajtó): {matched}"
    )


def test_hungarian_full_address_span_extender():
    """find_address_blocks extends through A épület, 4. emelet, 2/7. ajtó"""
    text = "1024 Budapest, Keleti Károly utca 18-24. A épület, 4. emelet, 2/7. ajtó"
    blocks = find_address_blocks(text, "hu")
    addrs_with_suffix = [b for b in blocks if "A épület" in b.matched_text or "4. emelet" in b.matched_text or "2/7. ajtó" in b.matched_text]
    assert len(addrs_with_suffix) >= 1


# --- Hungarian shortened address ---


def test_hungarian_shortened_address():
    """HU: Budapest, Keleti Károly 18-24., 2/7."""
    text = "Budapest, Keleti Károly 18-24., 2/7."
    addrs = _get_address_detections(text, "hu")
    assert len(addrs) >= 1
    matched = addrs[0].matched_text
    assert "18-24" in matched or "2/7" in matched


# --- English full address ---


def test_english_full_address_building_floor_unit():
    """EN: 78 King Street, Building A, Floor 4, Unit 2/7, Manchester M2 4WU"""
    text = "78 King Street, Building A, Floor 4, Unit 2/7, Manchester M2 4WU"
    addrs = _get_address_detections(text, "en")
    assert len(addrs) >= 1
    matched = addrs[0].matched_text
    assert "78" in matched or "King" in matched
    assert "Building A" in matched or "Floor 4" in matched or "Unit 2/7" in matched


def test_english_address_apt_flat():
    """EN: 2458 Westlake Avenue, Apt 4B, Seattle, WA 98109"""
    text = "2458 Westlake Avenue, Apt 4B, Seattle, WA 98109"
    addrs = _get_address_detections(text, "en")
    assert len(addrs) >= 1


def test_english_address_flat():
    """EN: 10 Downing Street, Flat 2, London SW1A 2AA"""
    text = "10 Downing Street, Flat 2, London SW1A 2AA"
    addrs = _get_address_detections(text, "en")
    assert len(addrs) >= 1


# --- English shortened address ---


def test_english_shortened_address():
    """EN: Manchester, King 78, Unit 2/7"""
    text = "Manchester, King 78, Unit 2/7"
    addrs = _get_address_detections(text, "en")
    assert len(addrs) >= 1


# --- Spanish full address ---


def test_spanish_full_address_edificio_piso_puerta():
    """ES: Calle Mayor 12, Edificio B, 4º piso, puerta 2/7, Madrid"""
    text = "Calle Mayor 12, Edificio B, 4º piso, puerta 2/7, Madrid"
    addrs = _get_address_detections(text, "es")
    assert len(addrs) >= 1
    matched = addrs[0].matched_text
    assert "12" in matched or "Mayor" in matched
    assert "Edificio" in matched or "piso" in matched or "puerta" in matched


def test_spanish_full_address_planta_puerta():
    """ES: Avenida Diagonal 245, Planta 3, Puerta 4, Barcelona"""
    text = "Avenida Diagonal 245, Planta 3, Puerta 4, Barcelona"
    addrs = _get_address_detections(text, "es")
    assert len(addrs) >= 1


def test_spanish_full_address_portal_piso():
    """ES: Calle de Serrano 88, Portal A, Piso 2, Puerta 5, Madrid"""
    text = "Calle de Serrano 88, Portal A, Piso 2, Puerta 5, Madrid"
    addrs = _get_address_detections(text, "es")
    assert len(addrs) >= 1


# --- Spanish shortened address ---


def test_spanish_shortened_address():
    """ES: Madrid, Mayor 12, Piso 4, Puerta 2/7"""
    text = "Madrid, Mayor 12, Piso 4, Puerta 2/7"
    addrs = _get_address_detections(text, "es")
    assert len(addrs) >= 1


# --- Date fragments must NOT be POSTAL_ADDRESS ---


def test_dob_context_not_postal_address_hu():
    """szül.: 1989-08-17 must be DATE_OF_BIRTH, not POSTAL_ADDRESS"""
    text = "Szül.: 1989-08-17"
    addrs = _get_address_detections(text, "hu")
    dobs = _get_dob_detections(text, "hu")
    assert len(addrs) == 0, f"1989-08-17 with szül. must NOT be POSTAL_ADDRESS, got: {addrs}"
    assert len(dobs) >= 1


def test_dob_context_not_postal_address_ddmmyyyy():
    """szül.: 17/08/1989 must be DATE_OF_BIRTH, not POSTAL_ADDRESS"""
    text = "Szül.: 17/08/1989"
    addrs = _get_address_detections(text, "hu")
    dobs = _get_dob_detections(text, "hu")
    assert len(addrs) == 0
    assert len(dobs) >= 1


def test_dob_context_not_postal_address_en():
    """DOB: 1989-08-17 must not be POSTAL_ADDRESS"""
    text = "Date of birth: 1989-08-17"
    addrs = _get_address_detections(text, "en")
    assert len(addrs) == 0


def test_dob_context_not_postal_address_es():
    """fecha de nacimiento: 03/02/1991 must not be POSTAL_ADDRESS"""
    text = "Fecha de nacimiento: 03/02/1991"
    addrs = _get_address_detections(text, "es")
    assert len(addrs) == 0


# --- Regression: existing address detection still works ---


def test_regression_spanish_calle_mayor():
    """ES: Calle Mayor 12, Madrid - existing pattern"""
    text = "Domicilio: Calle Mayor 12, Madrid."
    addrs = _get_address_detections(text, "es")
    assert len(addrs) >= 1
    assert "Mayor" in addrs[0].matched_text or "12" in addrs[0].matched_text


def test_regression_hungarian_iranyitoszam_varos():
    """HU: 1024 Budapest, ... - irányítószám + város"""
    text = "1024 Budapest, Szabadság út 22."
    addrs = _get_address_detections(text, "hu")
    assert len(addrs) >= 1


def test_uppercase_locality_between_address_parts_is_merged():
    """Két címrész között NAGYBETŰS helységszó legyen egy címblokk."""
    text = "Fő utca 12 BUDAPEST 3/2 ajtó"
    addrs = _get_address_detections(text, "hu")
    assert len(addrs) >= 1
    matched = addrs[0].matched_text
    assert "12" in matched
    assert "BUDAPEST" in matched
    assert "3/2" in matched


def test_month_name_context_is_date():
    """Hónapnév a kontextusban -> DATE (ha nem cím)."""
    text = "Találkozó ideje: 2025 február 18."
    analyzer = MultilingualAnalyzer()
    results = analyzer.analyze(text, "hu")
    types = {r.entity_type for r in results}
    assert EntityType.DATE in types


def test_ymd_range_1900_2900_is_date():
    """1900..2900 közötti YYYY-MM-DD mintát dátumként kezeljük."""
    text = "Rögzítve: 2899-12-31, ellenőrzés kész."
    analyzer = MultilingualAnalyzer()
    results = analyzer.analyze(text, "hu")
    types = {r.entity_type for r in results}
    assert EntityType.DATE in types or EntityType.DATE_OF_BIRTH in types


def test_previous_words_priority_for_identifier():
    """Előtte lévő 2-3 szó alapján azonosító felismerése."""
    text = "A belső ügyfél azonosító 778899."
    analyzer = MultilingualAnalyzer()
    results = analyzer.analyze(text, "hu")
    types = {r.entity_type for r in results}
    assert EntityType.CUSTOMER_ID in types
