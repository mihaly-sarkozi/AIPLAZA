# tests/unit/test_pii_gdpr_email_classifier.py
"""Tests for email classification: personal vs organizational vs role-based; exact policy outcomes."""
from __future__ import annotations

import pytest

from apps.knowledge.pii_gdpr.detectors.email_classifier import EmailClassifier, classify_email
from apps.knowledge.pii_gdpr.enums import EmailClassification, EntityType, RecommendedAction
from apps.knowledge.pii_gdpr.models import PolicyConfig
from apps.knowledge.pii_gdpr.policy.policy_engine import PolicyEngine

pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


@pytest.mark.release_acceptance
def test_classify_personal_free():
    cls, conf = classify_email("anna.kovacs@gmail.com")
    assert cls == EmailClassification.PERSONAL_FREE_PROVIDER
    assert conf >= 0.9


def test_classify_organizational_personal():
    cls, conf = classify_email("anna.kovacs@company.com")
    assert cls == EmailClassification.ORGANIZATIONAL_PERSONAL
    assert conf >= 0.7


def test_classify_role_based():
    cls, conf = classify_email("info@company.com")
    assert cls == EmailClassification.ROLE_BASED_ORGANIZATIONAL
    assert conf >= 0.7


def test_classify_role_support():
    cls, _ = classify_email("support@example.com")
    assert cls == EmailClassification.ROLE_BASED_ORGANIZATIONAL


@pytest.fixture
def classifier():
    return EmailClassifier()


def test_detector_returns_email_results(classifier):
    text = "Kapcsolattartó: info@company.hu"
    results = classifier.detect(text, "hu")
    assert len(results) >= 1
    assert results[0].entity_type == EntityType.EMAIL_ADDRESS
    assert results[0].email_classification == EmailClassification.ROLE_BASED_ORGANIZATIONAL


def test_detector_kovacs_example(classifier):
    text = "Kovács Anna email címe anna.kovacs@example.com, telefonszáma +36 30 123 4567."
    results = classifier.detect(text, "hu")
    emails = [r for r in results if r.entity_type == EntityType.EMAIL_ADDRESS]
    assert len(emails) >= 1
    assert "anna.kovacs@example.com" in [e.matched_text for e in emails]


# --- Exact policy decision outcomes (corporate vs personal) ---


@pytest.mark.release_acceptance
def test_policy_personal_email_always_masked():
    """anna.kovacs@gmail.com → MASK regardless of config."""
    engine = PolicyEngine(PolicyConfig(allow_organizational_emails=True, allow_role_based_emails=True))
    dets = EmailClassifier().detect("Contact anna.kovacs@gmail.com", "en")
    assert len(dets) == 1
    assert dets[0].email_classification == EmailClassification.PERSONAL_FREE_PROVIDER
    decisions = engine.decide_all(dets)
    assert decisions[0].recommended_action == RecommendedAction.MASK


def test_policy_organizational_personal_review_by_default():
    """anna.kovacs@company.com → REVIEW when allow_organizational_emails=True, action=review."""
    engine = PolicyEngine(PolicyConfig(allow_organizational_emails=True, email_organizational_personal_action="review"))
    dets = EmailClassifier().detect("Contact anna.kovacs@company.com", "en")
    assert len(dets) == 1
    assert dets[0].email_classification == EmailClassification.ORGANIZATIONAL_PERSONAL
    decisions = engine.decide_all(dets)
    assert decisions[0].recommended_action == RecommendedAction.REVIEW_REQUIRED


def test_policy_organizational_personal_masked_when_not_allowed():
    """anna.kovacs@company.com → MASK when allow_organizational_emails=False."""
    engine = PolicyEngine(PolicyConfig(allow_organizational_emails=False))
    dets = EmailClassifier().detect("Contact anna.kovacs@company.com", "en")
    decisions = engine.decide_all(dets)
    assert decisions[0].recommended_action == RecommendedAction.MASK


def test_policy_organizational_personal_mask_when_configured():
    """anna.kovacs@company.com → MASK when email_organizational_personal_action=mask."""
    engine = PolicyEngine(PolicyConfig(allow_organizational_emails=True, email_organizational_personal_action="mask"))
    dets = EmailClassifier().detect("Contact anna.kovacs@company.com", "en")
    decisions = engine.decide_all(dets)
    assert decisions[0].recommended_action == RecommendedAction.MASK


@pytest.mark.release_acceptance
def test_policy_role_based_keep_by_default():
    """info@company.com → KEEP when allow_role_based_emails=True."""
    engine = PolicyEngine(PolicyConfig(allow_role_based_emails=True, email_role_based_action="keep"))
    dets = EmailClassifier().detect("Email info@company.com for more.", "en")
    assert len(dets) == 1
    assert dets[0].email_classification == EmailClassification.ROLE_BASED_ORGANIZATIONAL
    decisions = engine.decide_all(dets)
    assert decisions[0].recommended_action == RecommendedAction.KEEP


@pytest.mark.release_acceptance
def test_policy_role_based_review_when_configured():
    """info@company.com → REVIEW when email_role_based_action=review."""
    engine = PolicyEngine(PolicyConfig(allow_role_based_emails=True, email_role_based_action="review"))
    dets = EmailClassifier().detect("Email info@company.com", "en")
    decisions = engine.decide_all(dets)
    assert decisions[0].recommended_action == RecommendedAction.REVIEW_REQUIRED


@pytest.mark.release_acceptance
def test_policy_role_based_masked_when_not_allowed():
    """info@company.com → REVIEW when allow_role_based_emails=False (not KEEP)."""
    engine = PolicyEngine(PolicyConfig(allow_role_based_emails=False))
    dets = EmailClassifier().detect("Email info@company.com", "en")
    decisions = engine.decide_all(dets)
    assert decisions[0].recommended_action == RecommendedAction.REVIEW_REQUIRED


# --- Pipeline: exact outcomes for document with all three email types ---


def test_pipeline_email_decisions_exact():
    """Full pipeline: assert exact policy decisions for personal, org personal, role-based emails."""
    from apps.knowledge.pii_gdpr.pipeline.ingestion_pipeline import IngestionPipeline

    policy_config = PolicyConfig(
        allow_organizational_emails=True,
        allow_role_based_emails=True,
        email_organizational_personal_action="review",
        email_role_based_action="keep",
    )
    pipeline = IngestionPipeline(policy_config=policy_config)
    text = (
        "Personal: anna.kovacs@gmail.com. "
        "Work: anna.kovacs@company.com. "
        "General: info@company.com."
    )
    out = pipeline.run(text)
    detections = out["raw_detections"]
    decisions = out["policy_decisions"]
    emails = [(d, dec) for d, dec in zip(detections, decisions) if d.entity_type == EntityType.EMAIL_ADDRESS]
    # We expect 3 emails; map by matched text to exact decision
    by_email = {d.matched_text: dec.recommended_action for d, dec in emails}
    assert by_email.get("anna.kovacs@gmail.com") == RecommendedAction.MASK
    assert by_email.get("anna.kovacs@company.com") == RecommendedAction.REVIEW_REQUIRED
    assert by_email.get("info@company.com") == RecommendedAction.KEEP
