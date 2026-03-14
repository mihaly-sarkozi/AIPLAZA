# tests/unit/test_context_scoring.py
"""Context-based scoring: edge cases (engine vs SKU, VIN vs random 17-char, plate vs product)."""
from __future__ import annotations

import pytest

from apps.knowledge.pii_gdpr.enums import EntityType, RecommendedAction
from apps.knowledge.pii_gdpr.scoring import (
    ContextScorer,
    context_score,
    composite_score,
    action_from_score,
    should_ignore_by_score,
    MASK_THRESHOLD,
    REVIEW_THRESHOLD,
    IGNORE_BELOW,
)
from apps.knowledge.pii_gdpr.pipeline.ingestion_pipeline import IngestionPipeline

pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


# --- Thresholds ---


def test_action_from_score_mask():
    assert action_from_score(0.85) == RecommendedAction.MASK
    assert action_from_score(0.90) == RecommendedAction.MASK


def test_action_from_score_review():
    assert action_from_score(0.60) == RecommendedAction.REVIEW_REQUIRED
    assert action_from_score(0.70) == RecommendedAction.REVIEW_REQUIRED
    assert action_from_score(0.84) == RecommendedAction.REVIEW_REQUIRED


def test_action_from_score_ignore():
    assert action_from_score(0.59) == RecommendedAction.IGNORE
    assert action_from_score(0.0) == RecommendedAction.IGNORE


def test_should_ignore_by_score():
    assert should_ignore_by_score(0.59) is True
    assert should_ignore_by_score(0.60) is False


def test_composite_score_clamp():
    assert composite_score(0.9, 0.2, 0) == 1.0
    assert composite_score(0.5, -0.6, 0) == 0.0


# --- Context score: positive vs negative keywords ---


def test_context_score_vin_positive():
    text = "Vehicle VIN: WVWZZZ1JZXW000001 found."
    # Span of "WVWZZZ1JZXW000001" (assume start=14, end=31)
    start = text.index("WVWZZZ1JZXW000001")
    end = start + len("WVWZZZ1JZXW000001")
    s = context_score(text, start, end, EntityType.VIN)
    assert s > 0


def test_context_score_vin_negative():
    text = "SKU product code: WVWZZZ1JZXW000001 in invoice."
    start = text.index("WVWZZZ1JZXW000001")
    end = start + len("WVWZZZ1JZXW000001")
    s = context_score(text, start, end, EntityType.VIN)
    assert s < 0


def test_context_score_engine_positive():
    text = "Engine number: AB12CD345678"
    start = text.index("AB12CD345678")
    end = start + len("AB12CD345678")
    s = context_score(text, start, end, EntityType.ENGINE_IDENTIFIER)
    assert s > 0


def test_context_score_engine_negative_sku():
    text = "SKU AB12CD345678 for product."
    start = text.index("AB12CD345678")
    end = start + len("AB12CD345678")
    s = context_score(text, start, end, EntityType.ENGINE_IDENTIFIER)
    assert s < 0


def test_context_score_plate_positive():
    text = "License plate: ABC-123"
    start = text.index("ABC-123")
    end = start + len("ABC-123")
    s = context_score(text, start, end, EntityType.VEHICLE_REGISTRATION)
    assert s > 0


def test_context_score_plate_negative_product():
    text = "Product code ABC-123 in invoice."
    start = text.index("ABC-123")
    end = start + len("ABC-123")
    s = context_score(text, start, end, EntityType.VEHICLE_REGISTRATION)
    assert s < 0


# --- Edge-case pipeline: engine number vs SKU ---


@pytest.mark.slow
def test_pipeline_engine_number_vs_sku():
    """Engine number in context → detected and high score; same pattern with SKU → low/dropped."""
    pipeline = IngestionPipeline()
    # Positive context: should keep engine detection
    text_engine = "Engine number: AB12CD345678"
    out_engine = pipeline.run(text_engine)
    engine_detections = [d for d in out_engine["raw_detections"] if d.entity_type == EntityType.ENGINE_IDENTIFIER]
    # With positive context we expect at least one and score >= review
    assert len(engine_detections) >= 1
    assert engine_detections[0].confidence_score >= REVIEW_THRESHOLD

    # Negative context (SKU): pattern might still match but score should be lower or dropped
    text_sku = "SKU AB12CD345678 product item."
    out_sku = pipeline.run(text_sku)
    sku_detections = [d for d in out_sku["raw_detections"] if d.entity_type == EntityType.ENGINE_IDENTIFIER]
    # Either no detection (below ignore) or low score
    if sku_detections:
        assert sku_detections[0].confidence_score < MASK_THRESHOLD


# --- Edge-case pipeline: VIN vs random 17-char ---


@pytest.mark.slow
def test_pipeline_vin_vs_random_17char():
    """VIN with label → high score; random 17-char without VIN context → lower or ignored."""
    pipeline = IngestionPipeline()
    text_labeled = "VIN: WVWZZZ1JZXW000001"
    out_labeled = pipeline.run(text_labeled)
    vin_labeled = [d for d in out_labeled["raw_detections"] if d.entity_type == EntityType.VIN]
    assert len(vin_labeled) >= 1
    assert vin_labeled[0].confidence_score >= MASK_THRESHOLD

    text_random = "Random code XYWZZZ1JZXW000001 end."
    out_random = pipeline.run(text_random)
    vin_random = [d for d in out_random["raw_detections"] if d.entity_type == EntityType.VIN]
    # Without positive context the composite score can be below mask; may be review or ignore
    if vin_random:
        assert vin_random[0].confidence_score <= 0.92  # no label boost


# --- Edge-case pipeline: license plate vs product code ---


@pytest.mark.slow
def test_pipeline_license_plate_vs_product_code():
    """License plate in context → detected; ABC-123 as product code → lower score or dropped."""
    pipeline = IngestionPipeline()
    text_plate = "Vehicle license plate: ABC-123"
    out_plate = pipeline.run(text_plate)
    plate_detections = [d for d in out_plate["raw_detections"] if d.entity_type == EntityType.VEHICLE_REGISTRATION]
    assert len(plate_detections) >= 1
    assert plate_detections[0].confidence_score >= REVIEW_THRESHOLD

    text_product = "Product ABC-123 invoice termék."
    out_product = pipeline.run(text_product)
    product_detections = [d for d in out_product["raw_detections"] if d.entity_type == EntityType.VEHICLE_REGISTRATION]
    if product_detections:
        assert product_detections[0].confidence_score < MASK_THRESHOLD or product_detections[0].recommended_action != RecommendedAction.MASK
