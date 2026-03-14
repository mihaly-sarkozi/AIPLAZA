# tests/unit/test_pii_gdpr_regex_detector.py
"""Tests for the regex-based PII detector."""
from __future__ import annotations

import pytest

from apps.knowledge.pii_gdpr.detectors.regex_detector import RegexDetector
from apps.knowledge.pii_gdpr.enums import EntityType

pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


@pytest.fixture
def detector():
    return RegexDetector()


@pytest.mark.release_acceptance
def test_detects_email(detector):
    text = "Contact: anna.kovacs@example.com for details."
    results = detector.detect(text, "en")
    emails = [r for r in results if r.entity_type == EntityType.EMAIL_ADDRESS]
    assert len(emails) >= 1
    assert any("anna.kovacs@example.com" in r.matched_text for r in emails)


@pytest.mark.release_acceptance
def test_detects_phone_hu(detector):
    text = "Telefonszáma: +36 30 123 4567."
    results = detector.detect(text, "hu")
    phones = [r for r in results if r.entity_type == EntityType.PHONE_NUMBER]
    assert len(phones) >= 1


@pytest.mark.release_acceptance
def test_detects_iban(detector):
    text = "IBAN: HU42 1177 3016 1111 1018 0000 0000"
    results = detector.detect(text, "en")
    ibans = [r for r in results if r.entity_type == EntityType.IBAN]
    assert len(ibans) >= 1


@pytest.mark.release_acceptance
def test_detects_customer_id(detector):
    text = "Ügyfél: UGY-12345 és CLIENT-99124."
    results = detector.detect(text, "hu")
    cust = [r for r in results if r.entity_type == EntityType.CUSTOMER_ID]
    assert len(cust) >= 1


@pytest.mark.release_acceptance
def test_detects_vehicle_registration(detector):
    text = "Rendszám: ABC-123."
    results = detector.detect(text, "hu")
    plates = [r for r in results if r.entity_type == EntityType.VEHICLE_REGISTRATION]
    assert len(plates) >= 1


@pytest.mark.release_acceptance
def test_detects_date_of_birth(detector):
    text = "Született: 1992. 03. 14."
    results = detector.detect(text, "hu")
    dobs = [r for r in results if r.entity_type == EntityType.DATE_OF_BIRTH]
    assert len(dobs) >= 1
