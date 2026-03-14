# tests/unit/test_pii_gdpr_vehicle_detector.py
"""Tests for vehicle-related detector: VIN, plate, engine number."""
from __future__ import annotations

import pytest

from apps.knowledge.pii_gdpr.detectors.vehicle_detector import VehicleDetector
from apps.knowledge.pii_gdpr.enums import EntityType

pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


@pytest.fixture
def detector():
    return VehicleDetector(context_window=80)


@pytest.mark.release_acceptance
def test_vin_labeled(detector):
    text = "John Smith's vehicle VIN is WVWZZZ1JZXW000001 and engine number is AB12CD345678."
    results = detector.detect(text, "en")
    vins = [r for r in results if r.entity_type == EntityType.VIN]
    assert len(vins) >= 1
    assert any("WVWZZZ1JZXW000001" in r.matched_text for r in vins)


def test_engine_number_in_context(detector):
    text = "Engine number: AB12CD345678"
    results = detector.detect(text, "en")
    engines = [r for r in results if r.entity_type == EntityType.ENGINE_IDENTIFIER]
    assert len(engines) >= 1


@pytest.mark.release_acceptance
def test_spanish_plate(detector):
    text = "Juan Pérez vive en Calle Mayor 12, Madrid y su matrícula es 1234 ABC."
    results = detector.detect(text, "es")
    plates = [r for r in results if r.entity_type == EntityType.VEHICLE_REGISTRATION]
    assert len(plates) >= 1
    assert any("1234 ABC" in r.matched_text for r in plates)


@pytest.mark.release_acceptance
def test_hu_plate(detector):
    text = "Rendszám: ABC-123."
    results = detector.detect(text, "hu")
    plates = [r for r in results if r.entity_type == EntityType.VEHICLE_REGISTRATION]
    assert len(plates) >= 1
