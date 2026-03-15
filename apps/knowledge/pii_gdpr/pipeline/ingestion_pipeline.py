# apps/knowledge/pii_gdpr/pipeline/ingestion_pipeline.py
"""
End-to-end ingestion pipeline: raw text -> language detection -> detectors -> merge -> policy -> sanitize -> output.
"""
from __future__ import annotations

from typing import List, Optional

from apps.knowledge.pii_gdpr.models import (
    AnalyzerConfig,
    PolicyConfig,
    DetectionResult,
    DetectionSummary,
    SanitizationResult,
    PolicyDecision,
)
from apps.knowledge.pii_gdpr.pipeline.multilingual_analyzer import MultilingualAnalyzer, detect_language
from apps.knowledge.pii_gdpr.policy.policy_engine import PolicyEngine
from apps.knowledge.pii_gdpr.policy.legacy_mapping import get_legacy_name
from apps.knowledge.pii_gdpr.sanitization.sanitizer import Sanitizer
from apps.knowledge.pii_gdpr.enums import RecommendedAction, RiskClass


class IngestionPipeline:
    """
    Full pipeline: raw text in -> raw detections, normalized detections, policy decisions,
    sanitized text, summary statistics.
    """

    def __init__(
        self,
        analyzer_config: Optional[AnalyzerConfig] = None,
        policy_config: Optional[PolicyConfig] = None,
    ):
        self.analyzer_config = analyzer_config or AnalyzerConfig()
        self.policy_config = policy_config or PolicyConfig()
        self.analyzer = MultilingualAnalyzer(self.analyzer_config)
        self.policy_engine = PolicyEngine(self.policy_config)
        self.sanitizer = Sanitizer()

    def run(
        self,
        raw_text: str,
        language: Optional[str] = None,
    ) -> dict:
        """
        Run the full pipeline.
        Returns dict with: raw_detections, normalized_detections, policy_decisions,
        sanitized_text, sanitization_result, summary, language.
        """
        lang = language or detect_language(raw_text)
        raw_detections = self.analyzer.analyze(raw_text, lang)
        # Egyetlen policy: sensitivity (weak/medium/strong) a scope – csak ezek a típusok maradnak
        if getattr(self.policy_config, "sensitivity", None):
            from apps.knowledge.pii_gdpr.entity_registry import get_sensitivity_set
            allowed = get_sensitivity_set(self.policy_config.sensitivity)
            raw_detections = [d for d in raw_detections if get_legacy_name(d.entity_type) in allowed]
        policy_decisions = self.policy_engine.decide_all(raw_detections)
        summary = self._build_summary(raw_detections, policy_decisions, raw_text, lang)
        sanitization_result = self.sanitizer.sanitize(
            raw_text, raw_detections, policy_decisions, summary
        )
        return {
            "raw_detections": raw_detections,
            "normalized_detections": raw_detections,
            "policy_decisions": policy_decisions,
            "sanitized_text": sanitization_result.sanitized_text,
            "sanitization_result": sanitization_result,
            "summary": summary,
            "language": lang,
        }

    def _build_summary(
        self,
        detections: List[DetectionResult],
        decisions: List[PolicyDecision],
        raw_text: str,
        language: str,
    ) -> DetectionSummary:
        by_entity: dict[str, int] = {}
        by_risk: dict[str, int] = {}
        by_action: dict[str, int] = {}
        for d in detections:
            by_entity[d.entity_type.value] = by_entity.get(d.entity_type.value, 0) + 1
            by_risk[d.risk_level.value] = by_risk.get(d.risk_level.value, 0) + 1
        for dec in decisions:
            by_action[dec.recommended_action.value] = by_action.get(dec.recommended_action.value, 0) + 1
        sanitized_len = 0  # will be set by sanitizer
        return DetectionSummary(
            total_detections=len(detections),
            by_entity_type=by_entity,
            by_risk_class=by_risk,
            by_action=by_action,
            language=language,
            document_length=len(raw_text),
            sanitized_length=sanitized_len,
        )
