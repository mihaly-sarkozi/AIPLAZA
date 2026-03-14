# apps/knowledge/pii_gdpr/models.py
"""
Pydantic models for PII/GDPR detection pipeline.
"""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

# Explicit policy döntések role-based / organizational emailre (konfigurálható)
EmailRoleBasedAction = Literal["keep", "review", "mask"]
EmailOrganizationalAction = Literal["keep", "review", "generalize", "mask"]

from apps.knowledge.pii_gdpr.enums import (
    EmailClassification as EmailClassificationEnum,
    EntityType,
    RecommendedAction,
    RiskClass,
)


class DetectionResult(BaseModel):
    """Single PII detection with full metadata."""

    entity_type: EntityType
    matched_text: str
    start: int
    end: int
    language: str = "en"
    source_detector: str
    confidence_score: float = Field(ge=0.0, le=1.0)
    risk_level: RiskClass = RiskClass.UNCERTAIN
    recommended_action: RecommendedAction = RecommendedAction.REVIEW_REQUIRED
    context_before: Optional[str] = None
    context_after: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def length(self) -> int:
        return self.end - self.start


class EmailDetectionResult(DetectionResult):
    """Detection result with email-specific classification."""

    email_classification: Optional[EmailClassificationEnum] = None
    email_classification_confidence: Optional[float] = None


class PolicyDecision(BaseModel):
    """Policy engine output for a single detection."""

    detection_id: Optional[str] = None
    entity_type: EntityType
    risk_class: RiskClass
    recommended_action: RecommendedAction
    allow_organizational_email: bool = False
    allow_role_based_email: bool = False
    reason: Optional[str] = None


class DetectionSummary(BaseModel):
    """Summary statistics of a detection run."""

    total_detections: int = 0
    by_entity_type: dict[str, int] = Field(default_factory=dict)
    by_risk_class: dict[str, int] = Field(default_factory=dict)
    by_action: dict[str, int] = Field(default_factory=dict)
    language: str = "en"
    document_length: int = 0
    sanitized_length: int = 0


class SanitizationResult(BaseModel):
    """Result of sanitizing text."""

    sanitized_text: str
    raw_text: str
    replacements: list[tuple[int, int, str, str]] = Field(
        default_factory=list,
        description="(start, end, original_snippet, placeholder)",
    )
    preserved_offsets: bool = True
    summary: Optional[DetectionSummary] = None


class AnalyzerConfig(BaseModel):
    """Configuration for the multilingual analyzer."""

    supported_languages: list[str] = Field(default_factory=lambda: ["en", "hu", "es"])
    enable_ner: bool = True
    enable_regex: bool = True
    enable_context: bool = True
    enable_email_classifier: bool = True
    enable_vehicle_detector: bool = True
    enable_technical_detector: bool = True
    context_window_chars: int = 50
    # Score thresholds (context-based: 0.85+ mask, 0.60–0.84 review, below 0.60 ignore)
    mask_threshold: float = 0.85
    review_threshold: float = 0.60
    low_confidence_threshold: float = 0.40
    ignore_below: float = 0.60


class PolicyConfig(BaseModel):
    """Configuration for the policy engine. Egyetlen policy engine: pii_gdpr."""

    mode: str = "balanced"  # strict | balanced | permissive
    # Ha megadva (weak|medium|strong), a pipeline csak ezeket a legacy típusokat adja (entities_for_sensitivity)
    sensitivity: Optional[str] = None
    allowlist_entities: list[str] = Field(default_factory=list)
    denylist_entities: list[str] = Field(default_factory=list)
    allow_organizational_emails: bool = True
    allow_role_based_emails: bool = True
    # Explicit policy döntés: role-based email (info@, support@, …) → pontosan ezt az action-t kapja
    email_role_based_action: EmailRoleBasedAction = "keep"
    # Organizational personal (név@ceg.hu) → action ha allow_organizational_emails
    email_organizational_personal_action: EmailOrganizationalAction = "review"
    allow_dates: bool = False
    allow_organization_names: bool = True
    allow_locations: bool = False
    entity_to_risk_map: dict[str, str] = Field(default_factory=dict)
    risk_to_action_map: dict[str, str] = Field(default_factory=dict)
