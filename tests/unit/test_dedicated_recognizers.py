# tests/unit/test_dedicated_recognizers.py
"""Positive, negative, and edge-case tests for dedicated recognizers."""
from __future__ import annotations

import pytest

from apps.knowledge.pii_gdpr.enums import EntityType
from apps.knowledge.pii_gdpr.detectors import (
    IPRecognizer,
    MACRecognizer,
    IMEIRecognizer,
    VINRecognizer,
    EngineIDRecognizer,
    BankAccountRecognizer,
    DocumentIdentifiersRecognizer,
)

pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


# --- IP ---


class TestIPRecognizer:
    @pytest.mark.release_acceptance
    def test_positive_ipv4(self):
        r = IPRecognizer()
        out = r.detect("Server at 192.168.1.10 responded.", "en")
        assert len(out) >= 1
        assert any(d.entity_type == EntityType.IP_ADDRESS and "192.168.1.10" in d.matched_text for d in out)

    def test_positive_ipv6(self):
        r = IPRecognizer()
        out = r.detect("Host: 2001:0db8:85a3:0000:0000:8a2e:0370:7334", "en")
        assert len(out) >= 1
        assert any(d.entity_type == EntityType.IP_ADDRESS for d in out)

    def test_negative_no_ip(self):
        r = IPRecognizer()
        out = r.detect("No numbers or addresses here.", "en")
        assert len(out) == 0

    def test_edge_ipv4_like_version(self):
        r = IPRecognizer()
        # 1.2.3.4 can be version number; we still detect (recognizer does not validate 0-255)
        out = r.detect("Version 1.2.3.4 released.", "en")
        assert len(out) >= 1


# --- MAC ---


class TestMACRecognizer:
    @pytest.mark.release_acceptance
    def test_positive_colon(self):
        r = MACRecognizer()
        out = r.detect("MAC: 00:1A:2B:3C:4D:5E", "en")
        assert len(out) >= 1
        assert any(d.entity_type == EntityType.MAC_ADDRESS and "00:1A:2B:3C:4D:5E" in d.matched_text for d in out)

    def test_positive_hyphen(self):
        r = MACRecognizer()
        out = r.detect("Address 00-1A-2B-3C-4D-5E", "en")
        assert len(out) >= 1

    def test_negative_no_mac(self):
        r = MACRecognizer()
        out = r.detect("Random text 12345.", "en")
        assert len(out) == 0

    def test_edge_lowercase(self):
        r = MACRecognizer()
        out = r.detect("mac aa:bb:cc:dd:ee:ff", "en")
        assert len(out) >= 1


# --- IMEI ---


class TestIMEIRecognizer:
    @pytest.mark.release_acceptance
    def test_positive_labeled(self):
        r = IMEIRecognizer()
        out = r.detect("IMEI: 490154203237518", "en")
        assert len(out) >= 1
        assert any(d.entity_type == EntityType.IMEI and "490154203237518" in d.matched_text for d in out)

    def test_positive_standalone_15_digits(self):
        r = IMEIRecognizer()
        out = r.detect("Device 490154203237518 registered.", "en")
        assert len(out) >= 1

    def test_negative_not_15_digits(self):
        r = IMEIRecognizer()
        out = r.detect("ID 12345678901234 is 14 digits.", "en")
        assert not any(d.entity_type == EntityType.IMEI for d in out)

    def test_edge_imei_lowercase_label(self):
        r = IMEIRecognizer()
        out = r.detect("imei: 490154203237518", "en")
        assert len(out) >= 1


# --- VIN ---


class TestVINRecognizer:
    @pytest.mark.release_acceptance
    def test_positive_labeled(self):
        r = VINRecognizer()
        out = r.detect("VIN: WVWZZZ1JZXW000001", "en")
        assert len(out) >= 1
        assert any(d.entity_type == EntityType.VIN and "WVWZZZ1JZXW000001" in d.matched_text for d in out)

    def test_positive_standalone_17(self):
        r = VINRecognizer()
        out = r.detect("Chassis WVWZZZ1JZXW000001.", "en")
        assert len(out) >= 1

    def test_negative_16_chars(self):
        r = VINRecognizer()
        out = r.detect("Code WVWZZZ1JZXW00000 has 16 chars.", "en")
        assert not any(d.entity_type == EntityType.VIN for d in out)

    def test_edge_no_ioq(self):
        r = VINRecognizer()
        # VIN excludes I,O,Q
        out = r.detect("VIN: 1HGBH41JXMN109186", "en")
        assert len(out) >= 1


# --- Engine / Chassis ---


class TestEngineIDRecognizer:
    def test_positive_engine_number(self):
        r = EngineIDRecognizer()
        out = r.detect("Engine number: AB12CD345678", "en")
        assert len(out) >= 1
        assert any(d.entity_type == EntityType.ENGINE_IDENTIFIER for d in out)

    def test_positive_chassis(self):
        r = EngineIDRecognizer()
        out = r.detect("Chassis: XYZ987654321", "en")
        assert len(out) >= 1
        assert any(d.entity_type == EntityType.CHASSIS_IDENTIFIER for d in out)

    def test_positive_motorszam_hu(self):
        r = EngineIDRecognizer()
        out = r.detect("Motorszám: AB12CD345678", "hu")
        assert len(out) >= 1

    def test_negative_unlabeled_digits(self):
        r = EngineIDRecognizer()
        out = r.detect("Code AB12CD345678 without label.", "en")
        assert not any(d.entity_type == EntityType.ENGINE_IDENTIFIER for d in out)

    def test_edge_alvazszam(self):
        r = EngineIDRecognizer()
        out = r.detect("Alvázszám: CH12345678", "hu")
        assert len(out) >= 1
        assert any(d.entity_type == EntityType.CHASSIS_IDENTIFIER for d in out)


# --- Bank account ---


class TestBankAccountRecognizer:
    def test_positive_hu_888(self):
        r = BankAccountRecognizer()
        out = r.detect("Account 123456781234567812345678", "en")
        assert len(out) >= 1
        assert any(d.entity_type == EntityType.BANK_ACCOUNT_NUMBER for d in out)

    def test_positive_hu_dashes(self):
        r = BankAccountRecognizer()
        out = r.detect("SZámla: 12345678-12345678-12345678", "hu")
        assert len(out) >= 1

    def test_positive_labeled_account(self):
        r = BankAccountRecognizer()
        out = r.detect("Account: 12345678901234", "en")
        assert len(out) >= 1

    def test_negative_short_number(self):
        r = BankAccountRecognizer()
        out = r.detect("Short 123456789.", "en")
        assert not any(d.entity_type == EntityType.BANK_ACCOUNT_NUMBER for d in out)

    def test_edge_szamla_space(self):
        r = BankAccountRecognizer()
        out = r.detect("Bankszámla 111111112222222233333333", "hu")
        assert len(out) >= 1


# --- Document identifiers ---


class TestDocumentIdentifiersRecognizer:
    def test_positive_taj(self):
        r = DocumentIdentifiersRecognizer()
        out = r.detect("TAJ: 123 456 789", "hu")
        assert len(out) >= 1
        assert any(d.entity_type == EntityType.PERSONAL_ID for d in out)

    def test_positive_tax_id(self):
        r = DocumentIdentifiersRecognizer()
        out = r.detect("Adóazonosító: 12345678-1-12", "hu")
        assert len(out) >= 1
        assert any(d.entity_type == EntityType.TAX_ID for d in out)

    def test_positive_passport(self):
        r = DocumentIdentifiersRecognizer()
        out = r.detect("Passport: AB1234567", "en")
        assert len(out) >= 1
        assert any(d.entity_type == EntityType.PASSPORT_NUMBER for d in out)

    def test_positive_driver_license(self):
        r = DocumentIdentifiersRecognizer()
        out = r.detect("Driver license: DL123456", "en")
        assert len(out) >= 1
        assert any(d.entity_type == EntityType.DRIVER_LICENSE_NUMBER for d in out)

    def test_negative_plain_digits(self):
        r = DocumentIdentifiersRecognizer()
        out = r.detect("Just 123456789 and 12345678112.", "en")
        # May match TAJ (9 digits) or tax (8-1-2); no passport/driver without label
        assert not any(d.entity_type == EntityType.PASSPORT_NUMBER for d in out)
        assert not any(d.entity_type == EntityType.DRIVER_LICENSE_NUMBER for d in out)

    def test_edge_utlevel_hu(self):
        r = DocumentIdentifiersRecognizer()
        out = r.detect("Útlevél: XY123456", "hu")
        assert len(out) >= 1
        assert any(d.entity_type == EntityType.PASSPORT_NUMBER for d in out)
