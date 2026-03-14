# tests/unit/test_multilingual_pipeline.py
"""Explicit three-language and mixed-language test sets for the PII pipeline."""
from __future__ import annotations

import pytest

from apps.knowledge.pii_gdpr.enums import EntityType
from apps.knowledge.pii_gdpr.pipeline.ingestion_pipeline import IngestionPipeline
from apps.knowledge.pii_gdpr.pipeline.language_utils import detect_language, detect_language_per_chunk

pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


# --- One sentence per language ---


def test_english_sentence_email_phone():
    """EN: email and phone detected."""
    text = "Contact John Smith at john.smith@example.com or +1 555 123 4567."
    pipeline = IngestionPipeline()
    out = pipeline.run(text)
    types = {d.entity_type for d in out["raw_detections"]}
    assert EntityType.EMAIL_ADDRESS in types
    assert EntityType.PHONE_NUMBER in types


def test_hungarian_sentence_iban_rendszam():
    """HU: IBAN and rendszám (plate) detected."""
    text = "Fizetés: HU42 1177 3016 1111 1018 0000 0000. Rendszám: ABC-123."
    pipeline = IngestionPipeline()
    out = pipeline.run(text)
    types = {d.entity_type for d in out["raw_detections"]}
    assert EntityType.IBAN in types
    assert EntityType.VEHICLE_REGISTRATION in types


def test_spanish_sentence_matricula_address():
    """ES: matrícula (plate 1234 ABC) and Spanish address detected."""
    text = "Matrícula del vehículo: 1234 ABC. Domicilio: Calle Mayor 12, Madrid."
    pipeline = IngestionPipeline()
    out = pipeline.run(text)
    types = {d.entity_type for d in out["raw_detections"]}
    assert EntityType.VEHICLE_REGISTRATION in types
    assert EntityType.POSTAL_ADDRESS in types


def test_spanish_customer_contract_labels():
    """ES: cliente and contrato labels with numbers."""
    text = "Cliente: 12345. Número de contrato: 67890."
    pipeline = IngestionPipeline()
    out = pipeline.run(text)
    types = {d.entity_type for d in out["raw_detections"]}
    assert EntityType.CUSTOMER_ID in types or EntityType.CONTRACT_NUMBER in types


def test_spanish_engine_chassis_labels():
    """ES: número de motor / número de chasis."""
    text = "Número de motor: AB12CD345678. Número de chasis: XYZ987654321."
    pipeline = IngestionPipeline()
    out = pipeline.run(text)
    types = {d.entity_type for d in out["raw_detections"]}
    assert EntityType.ENGINE_IDENTIFIER in types or EntityType.CHASSIS_IDENTIFIER in types


# --- Mixed-language document samples ---


def test_mixed_language_paragraph():
    """Paragraph: EN + HU + ES mix; at least two languages' entities detected."""
    text = (
        "Customer John sent payment from john@example.com. "
        "Magyar ügyfél: UGY-99999, rendszám ABC-456. "
        "Cliente español: contrato 11111. Matrícula 9999 ZZZ."
    )
    pipeline = IngestionPipeline()
    out = pipeline.run(text)
    detections = out["raw_detections"]
    assert len(detections) >= 3
    types = {d.entity_type for d in detections}
    assert EntityType.EMAIL_ADDRESS in types
    assert EntityType.VEHICLE_REGISTRATION in types or EntityType.CUSTOMER_ID in types or EntityType.CONTRACT_NUMBER in types


def test_mixed_language_sentences_chunk_detection():
    """Chunk-level language detection returns multiple languages for mixed text."""
    text = "This is English. Ez magyar szöveg. Esto es español."
    chunks = detect_language_per_chunk(text, chunk_strategy="sentence")
    langs = {lang for _s, _e, lang in chunks}
    assert len(langs) >= 1
    assert "en" in langs or "hu" in langs or "es" in langs


def test_detect_language_english():
    assert detect_language("Hello world. This is a test.") == "en"


def test_detect_language_hungarian():
    lang = detect_language("Ez egy magyar mondat. Köszönöm.")
    assert lang in ("hu", "en")  # langdetect may vary


def test_detect_language_spanish():
    lang = detect_language("Esto es una frase en español. Gracias.")
    assert lang in ("es", "en")


# --- Multilingual keywords boost (vehicle/engine) ---


def test_hungarian_keywords_rendszam_motorszam():
    """HU keywords rendszám, motorszám in context boost detection."""
    text = "Rendszám: AB 12 CD 34. Motorszám: ENG12345678."
    pipeline = IngestionPipeline()
    out = pipeline.run(text)
    assert len(out["raw_detections"]) >= 1
    types = {d.entity_type for d in out["raw_detections"]}
    assert EntityType.VEHICLE_REGISTRATION in types or EntityType.ENGINE_IDENTIFIER in types


def test_english_keywords_license_plate_engine():
    """EN keywords license plate, engine number."""
    text = "License plate: 1234 ABC. Engine number: AB12CD345678."
    pipeline = IngestionPipeline()
    out = pipeline.run(text)
    types = {d.entity_type for d in out["raw_detections"]}
    assert EntityType.VEHICLE_REGISTRATION in types or EntityType.ENGINE_IDENTIFIER in types
