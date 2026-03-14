# tests/unit/test_pii_gdpr_pipeline.py
"""End-to-end and sanitizer tests for the PII/GDPR pipeline."""
from __future__ import annotations

import pytest

from apps.knowledge.pii_gdpr.pipeline.ingestion_pipeline import IngestionPipeline
from apps.knowledge.pii_gdpr.pipeline.multilingual_analyzer import merge_and_dedupe
from apps.knowledge.pii_gdpr.models import DetectionResult, AnalyzerConfig, PolicyConfig, EmailDetectionResult
from apps.knowledge.pii_gdpr.enums import EntityType, RecommendedAction, EmailClassification
from apps.knowledge.pii_gdpr.sanitization.sanitizer import Sanitizer
from apps.knowledge.pii_gdpr.detectors.technical_identifier_detector import TechnicalIdentifierDetector

pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


@pytest.mark.slow
def test_pipeline_kovacs_hungarian():
    """Magyar szöveg → nyelvnek hu-nak kell lennie (Kovács Anna, email címe, telefonszáma)."""
    text = "Kovács Anna email címe anna.kovacs@example.com, telefonszáma +36 30 123 4567."
    pipeline = IngestionPipeline()
    out = pipeline.run(text)
    assert out["language"] == "hu", f"Magyar szöveg esetén language legyen 'hu', kaptunk: {out['language']!r}"
    assert len(out["raw_detections"]) >= 1
    assert out["sanitized_text"] != text or len(out["raw_detections"]) == 0
    assert "summary" in out
    assert out["summary"].total_detections >= 1


@pytest.mark.slow
def test_pipeline_spanish_matricula():
    """Spanyol matrícula (1234 ABC) → rendszám típusú detektálás kötelező."""
    text = "Juan Pérez vive en Calle Mayor 12, Madrid y su matrícula es 1234 ABC."
    pipeline = IngestionPipeline()
    out = pipeline.run(text)
    assert len(out["raw_detections"]) >= 1
    entity_types = [d.entity_type for d in out["raw_detections"]]
    assert EntityType.VEHICLE_REGISTRATION in entity_types, (
        f"A '1234 ABC' spanyol rendszámnak kell detektálódnia (VEHICLE_REGISTRATION); "
        f"találatok típusai: {entity_types}"
    )


@pytest.mark.slow
def test_pipeline_vin_engine():
    text = "John Smith's vehicle VIN is WVWZZZ1JZXW000001 and engine number is AB12CD345678."
    pipeline = IngestionPipeline()
    out = pipeline.run(text)
    vins = [d for d in out["raw_detections"] if d.entity_type == EntityType.VIN]
    assert len(vins) >= 1


@pytest.mark.slow
def test_pipeline_imei_mac():
    text = "IMEI: 490154203237518, MAC: 00:1A:2B:3C:4D:5E"
    pipeline = IngestionPipeline()
    out = pipeline.run(text)
    tech = [d for d in out["raw_detections"] if d.entity_type in (EntityType.IMEI, EntityType.MAC_ADDRESS)]
    assert len(tech) >= 2


@pytest.mark.slow
def test_pipeline_info_company_email():
    """info@company.hu: explicit email_role_based_action='mask' → maszkolódik, nincs a kimenetben."""
    text = "Kapcsolattartó: info@company.hu"
    pipeline = IngestionPipeline(
        policy_config=PolicyConfig(mode="balanced", email_role_based_action="mask"),
    )
    out = pipeline.run(text)
    assert len(out["raw_detections"]) >= 1
    decisions = out["policy_decisions"]
    detections = out["raw_detections"]
    email_pairs = [(d, dec) for d, dec in zip(detections, decisions) if d.entity_type == EntityType.EMAIL_ADDRESS]
    assert len(email_pairs) >= 1, "Legalább egy email detektálódjon"
    assert "info@company.hu" not in out["sanitized_text"], (
        "email_role_based_action='mask' esetén a sanitized szöveg ne tartalmazzon nyers email címet"
    )
    assert "[EMAIL_ADDRESS]" in out["sanitized_text"] or "email" in out["sanitized_text"].lower(), (
        "Placeholder vagy maszk jelenjen meg az email helyén"
    )


@pytest.mark.slow
def test_role_based_email_policy_decision_explicit():
    """
    Role-based email (info@, support@) policy döntése konfigurálható és explicit.
    email_role_based_action='keep' → KEEP, email marad; 'mask' → MASK, email helyett placeholder.
    """
    text = "Írj nekünk: info@company.hu"
    # keep: a policy döntés KEEP, az email bent marad a kimenetben
    pipeline_keep = IngestionPipeline(
        policy_config=PolicyConfig(allow_role_based_emails=True, email_role_based_action="keep"),
    )
    out_keep = pipeline_keep.run(text)
    email_detections_keep = [d for d in out_keep["raw_detections"] if d.entity_type == EntityType.EMAIL_ADDRESS]
    email_decisions_keep = [
        dec for d, dec in zip(out_keep["raw_detections"], out_keep["policy_decisions"])
        if d.entity_type == EntityType.EMAIL_ADDRESS
    ]
    assert len(email_detections_keep) >= 1
    assert len(email_decisions_keep) >= 1
    assert email_decisions_keep[0].recommended_action == RecommendedAction.KEEP, (
        "email_role_based_action='keep' esetén a role-based email döntése KEEP"
    )
    assert "info@company.hu" in out_keep["sanitized_text"], (
        "KEEP esetén az email maradjon a sanitized szövegben"
    )
    # Opcionálisan: ellenőrizzük, hogy role-based-ként lett osztályozva (ha EmailDetectionResult)
    if isinstance(email_detections_keep[0], EmailDetectionResult) and email_detections_keep[0].email_classification:
        assert email_detections_keep[0].email_classification == EmailClassification.ROLE_BASED_ORGANIZATIONAL

    # mask: a policy döntés MASK, az email ne maradjon, placeholder legyen
    pipeline_mask = IngestionPipeline(
        policy_config=PolicyConfig(allow_role_based_emails=True, email_role_based_action="mask"),
    )
    out_mask = pipeline_mask.run(text)
    email_decisions_mask = [
        dec for d, dec in zip(out_mask["raw_detections"], out_mask["policy_decisions"])
        if d.entity_type == EntityType.EMAIL_ADDRESS
    ]
    assert len(email_decisions_mask) >= 1
    assert email_decisions_mask[0].recommended_action == RecommendedAction.MASK, (
        "email_role_based_action='mask' esetén a role-based email döntése MASK"
    )
    assert "info@company.hu" not in out_mask["sanitized_text"]
    assert "[EMAIL_ADDRESS]" in out_mask["sanitized_text"]


def test_merge_dedupe_overlapping():
    from apps.knowledge.pii_gdpr.enums import RiskClass
    a = DetectionResult(entity_type=EntityType.EMAIL_ADDRESS, matched_text="a@b.co", start=0, end=7, source_detector="r", confidence_score=0.9, risk_level=RiskClass.DIRECT_PII, recommended_action=RecommendedAction.MASK)
    b = DetectionResult(entity_type=EntityType.EMAIL_ADDRESS, matched_text="a@b.co", start=0, end=7, source_detector="e", confidence_score=0.95, risk_level=RiskClass.DIRECT_PII, recommended_action=RecommendedAction.MASK)
    merged = merge_and_dedupe([a, b])
    assert len(merged) == 1
    assert merged[0].confidence_score == 0.95


def test_sanitizer_mask():
    from apps.knowledge.pii_gdpr.models import PolicyDecision
    from apps.knowledge.pii_gdpr.enums import RiskClass
    raw = "Email: test@example.com"
    # Offsets: "test@example.com" is 7:22 in raw
    det = DetectionResult(entity_type=EntityType.EMAIL_ADDRESS, matched_text="test@example.com", start=7, end=7 + len("test@example.com"), source_detector="r", confidence_score=0.95, risk_level=RiskClass.DIRECT_PII, recommended_action=RecommendedAction.MASK)
    dec = PolicyDecision(entity_type=EntityType.EMAIL_ADDRESS, risk_class=RiskClass.DIRECT_PII, recommended_action=RecommendedAction.MASK)
    result = Sanitizer().sanitize(raw, [det], [dec])
    assert "Email: " in result.sanitized_text
    assert "[EMAIL_ADDRESS]" in result.sanitized_text
    assert "test@example.com" not in result.sanitized_text
    assert result.raw_text == raw
    assert len(result.replacements) == 1


def test_technical_detector_imei_mac():
    det = TechnicalIdentifierDetector()
    text = "IMEI: 490154203237518, MAC: 00:1A:2B:3C:4D:5E"
    results = det.detect(text, "en")
    assert len(results) >= 2


def test_legacy_pii_adapter_contract():
    """Legacy pii API (filter_pii, apply_pii_replacements) uses pii_gdpr via adapter."""
    from apps.knowledge.pii import filter_pii, apply_pii_replacements

    text = "Contact: user@example.com and +36 30 123 4567."
    matches = filter_pii(text, "medium")
    assert len(matches) >= 2
    types = {m[2] for m in matches}
    assert "email" in types
    assert "telefonszám" in types
    refs = [f"r{i}" for i in range(len(matches))]
    out = apply_pii_replacements(text, matches, refs)
    assert "user@example.com" not in out
    # Standard placeholders (pii.sanitization contract)
    assert "[EMAIL_ADDRESS]" in out or "[PHONE_NUMBER]" in out
