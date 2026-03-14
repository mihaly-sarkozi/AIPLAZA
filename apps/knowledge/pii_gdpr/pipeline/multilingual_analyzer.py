# apps/knowledge/pii_gdpr/pipeline/multilingual_analyzer.py
"""
Multilingual analyzer: chunk-level language detection for NER; regex/pattern detectors run language-independently.
"""
from __future__ import annotations

from typing import List, Optional

from apps.knowledge.pii_gdpr.models import AnalyzerConfig, DetectionResult
from apps.knowledge.pii_gdpr.detectors import (
    RegexDetector,
    NERDetector,
    ContextDetector,
    EmailClassifier,
    VehicleDetector,
    TechnicalIdentifierDetector,
    IPRecognizer,
    MACRecognizer,
    IMEIRecognizer,
    VINRecognizer,
    EngineIDRecognizer,
    BankAccountRecognizer,
    DocumentIdentifiersRecognizer,
)
from apps.knowledge.pii_gdpr.pipeline.language_utils import detect_language, detect_language_per_chunk
from apps.knowledge.pii_gdpr.scoring import (
    ContextScorer,
    CONTEXT_SENSITIVE_ENTITY_TYPES,
    IGNORE_BELOW,
    action_from_score,
)
from apps.knowledge.pii_gdpr.enums import RecommendedAction


def merge_and_dedupe(detections: List[DetectionResult]) -> List[DetectionResult]:
    """
    Merge overlapping spans: keep higher confidence; non-overlapping all kept.
    Sort by start, then by negative length (longer first). Process in order, skip if overlaps and lower confidence.
    """
    if not detections:
        return []
    sorted_d = sorted(detections, key=lambda x: (x.start, -(x.end - x.start)))
    merged: List[DetectionResult] = []
    for d in sorted_d:
        overlapping = [m for m in merged if m.start < d.end and m.end > d.start]
        if not overlapping:
            merged.append(d)
            continue
        best = max(overlapping, key=lambda m: m.confidence_score)
        if d.confidence_score > best.confidence_score:
            for m in overlapping:
                merged.remove(m)
            merged.append(d)
    return sorted(merged, key=lambda x: x.start)


class MultilingualAnalyzer:
    """Runs regex, NER (if available), context, email, vehicle, technical detectors and merges results."""

    def __init__(self, config: Optional[AnalyzerConfig] = None):
        self.config = config or AnalyzerConfig()
        self._regex = RegexDetector()
        self._ner = NERDetector()
        self._context = ContextDetector(window_chars=self.config.context_window_chars)
        self._email = EmailClassifier()
        self._vehicle = VehicleDetector(context_window=80)
        self._technical = TechnicalIdentifierDetector()
        self._ip = IPRecognizer()
        self._mac = MACRecognizer()
        self._imei = IMEIRecognizer()
        self._vin = VINRecognizer()
        self._engine_id = EngineIDRecognizer()
        self._bank_account = BankAccountRecognizer()
        self._document_id = DocumentIdentifiersRecognizer()
        self._context_scorer = ContextScorer(window=self.config.context_window_chars)

    def analyze(self, text: str, language: Optional[str] = None) -> List[DetectionResult]:
        """
        Run all detectors. Regex and pattern-based detectors run language-independently on full text.
        NER runs per chunk with chunk-level language detection for mixed-language content.
        """
        doc_lang = language or detect_language(text)
        if doc_lang not in self.config.supported_languages:
            doc_lang = "en"
        all_results: List[DetectionResult] = []

        # Pattern-based detectors: language-agnostic (run once on full text)
        if self.config.enable_regex:
            all_results.extend(self._regex.detect(text, doc_lang))
        if self.config.enable_context:
            all_results.extend(self._context.detect(text, doc_lang))
        if self.config.enable_email_classifier:
            all_results.extend(self._email.detect(text, doc_lang))
        if self.config.enable_vehicle_detector:
            all_results.extend(self._vehicle.detect(text, doc_lang))
        if self.config.enable_technical_detector:
            all_results.extend(self._technical.detect(text, doc_lang))
        all_results.extend(self._ip.detect(text, doc_lang))
        all_results.extend(self._mac.detect(text, doc_lang))
        all_results.extend(self._imei.detect(text, doc_lang))
        all_results.extend(self._vin.detect(text, doc_lang))
        all_results.extend(self._engine_id.detect(text, doc_lang))
        all_results.extend(self._bank_account.detect(text, doc_lang))
        all_results.extend(self._document_id.detect(text, doc_lang))

        # NER: per-chunk language so mixed-language text is handled correctly
        if self.config.enable_ner and self._ner.available():
            for start, end, chunk_lang in detect_language_per_chunk(text, chunk_strategy="sentence"):
                chunk_text = text[start:end]
                if not chunk_text.strip():
                    continue
                for d in self._ner.detect(chunk_text, chunk_lang):
                    all_results.append(
                        DetectionResult(
                            entity_type=d.entity_type,
                            matched_text=d.matched_text,
                            start=d.start + start,
                            end=d.end + start,
                            language=d.language,
                            source_detector=d.source_detector,
                            confidence_score=d.confidence_score,
                            risk_level=d.risk_level,
                            recommended_action=d.recommended_action,
                        )
                    )

        # Context-based rescoring for ambiguous types (VIN, engine, plate, customer ID, technical)
        for d in all_results:
            if d.entity_type in CONTEXT_SENSITIVE_ENTITY_TYPES:
                comp, action = self._context_scorer.rescore_detection(
                    text, d.confidence_score, d.start, d.end, d.entity_type
                )
                d.confidence_score = comp
                d.recommended_action = action

        # Thresholds: 0.85+ mask, 0.60–0.84 review, below 0.60 ignore (drop)
        threshold = max(self.config.ignore_below, IGNORE_BELOW)
        filtered = [d for d in all_results if d.confidence_score >= threshold]
        # Drop detections explicitly marked IGNORE (context rescore)
        filtered = [d for d in filtered if d.recommended_action != RecommendedAction.IGNORE]

        for d in filtered:
            if d.recommended_action == RecommendedAction.IGNORE:
                continue
            if d.confidence_score >= self.config.mask_threshold:
                d.recommended_action = RecommendedAction.MASK
            elif d.confidence_score >= self.config.review_threshold:
                d.recommended_action = RecommendedAction.REVIEW_REQUIRED

        return merge_and_dedupe(filtered)
