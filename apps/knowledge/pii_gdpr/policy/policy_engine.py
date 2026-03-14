# apps/knowledge/pii_gdpr/policy/policy_engine.py
"""
Policy engine: maps entities to risk classes and recommended actions.
Supports strict / balanced / permissive modes and configurable allow/deny and email rules.
"""
from __future__ import annotations

from typing import List, Optional

from apps.knowledge.pii_gdpr.enums import (
    EntityType,
    RiskClass,
    RecommendedAction,
    PolicyMode,
    EmailClassification,
)
from apps.knowledge.pii_gdpr.models import DetectionResult, PolicyConfig, PolicyDecision
from apps.knowledge.pii_gdpr.models import EmailDetectionResult

# Default entity -> risk (when not in config)
_DEFAULT_ENTITY_RISK: dict[EntityType, RiskClass] = {
    EntityType.PERSON_NAME: RiskClass.DIRECT_PII,
    EntityType.EMAIL_ADDRESS: RiskClass.DIRECT_PII,
    EntityType.PHONE_NUMBER: RiskClass.DIRECT_PII,
    EntityType.POSTAL_ADDRESS: RiskClass.DIRECT_PII,
    EntityType.DATE: RiskClass.INDIRECT_IDENTIFIER,
    EntityType.DATE_OF_BIRTH: RiskClass.DIRECT_PII,
    EntityType.PERSONAL_ID: RiskClass.DIRECT_PII,
    EntityType.TAX_ID: RiskClass.DIRECT_PII,
    EntityType.PASSPORT_NUMBER: RiskClass.DIRECT_PII,
    EntityType.DRIVER_LICENSE_NUMBER: RiskClass.DIRECT_PII,
    EntityType.IBAN: RiskClass.DIRECT_PII,
    EntityType.BANK_ACCOUNT_NUMBER: RiskClass.DIRECT_PII,
    EntityType.PAYMENT_CARD_NUMBER: RiskClass.DIRECT_PII,
    EntityType.IP_ADDRESS: RiskClass.INDIRECT_IDENTIFIER,
    EntityType.MAC_ADDRESS: RiskClass.INDIRECT_IDENTIFIER,
    EntityType.IMEI: RiskClass.INDIRECT_IDENTIFIER,
    EntityType.VEHICLE_REGISTRATION: RiskClass.INDIRECT_IDENTIFIER,
    EntityType.VIN: RiskClass.INDIRECT_IDENTIFIER,
    EntityType.ENGINE_IDENTIFIER: RiskClass.INDIRECT_IDENTIFIER,
    EntityType.CHASSIS_IDENTIFIER: RiskClass.INDIRECT_IDENTIFIER,
    EntityType.CUSTOMER_ID: RiskClass.INDIRECT_IDENTIFIER,
    EntityType.CONTRACT_NUMBER: RiskClass.INDIRECT_IDENTIFIER,
    EntityType.TICKET_ID: RiskClass.INDIRECT_IDENTIFIER,
    EntityType.EMPLOYEE_ID: RiskClass.INDIRECT_IDENTIFIER,
    EntityType.SESSION_ID: RiskClass.INDIRECT_IDENTIFIER,
    EntityType.DEVICE_ID: RiskClass.INDIRECT_IDENTIFIER,
    EntityType.HEALTH_DATA_HINT: RiskClass.SENSITIVE_DATA,
    EntityType.BIOMETRIC_HINT: RiskClass.SENSITIVE_DATA,
    EntityType.POLITICAL_OPINION_HINT: RiskClass.SENSITIVE_DATA,
    EntityType.RELIGION_HINT: RiskClass.SENSITIVE_DATA,
    EntityType.UNION_MEMBERSHIP_HINT: RiskClass.SENSITIVE_DATA,
    EntityType.SEXUAL_ORIENTATION_HINT: RiskClass.SENSITIVE_DATA,
}

# Default risk -> action by mode
_STRICT_ACTIONS: dict[RiskClass, RecommendedAction] = {
    RiskClass.DIRECT_PII: RecommendedAction.MASK,
    RiskClass.INDIRECT_IDENTIFIER: RecommendedAction.MASK,
    RiskClass.SENSITIVE_DATA: RecommendedAction.REVIEW_REQUIRED,
    RiskClass.LOW_RISK_ORG_DATA: RecommendedAction.GENERALIZE,
    RiskClass.UNCERTAIN: RecommendedAction.REVIEW_REQUIRED,
}
_BALANCED_ACTIONS: dict[RiskClass, RecommendedAction] = {
    RiskClass.DIRECT_PII: RecommendedAction.MASK,
    RiskClass.INDIRECT_IDENTIFIER: RecommendedAction.REVIEW_REQUIRED,
    RiskClass.SENSITIVE_DATA: RecommendedAction.REVIEW_REQUIRED,
    RiskClass.LOW_RISK_ORG_DATA: RecommendedAction.KEEP,
    RiskClass.UNCERTAIN: RecommendedAction.REVIEW_REQUIRED,
}
_PERMISSIVE_ACTIONS: dict[RiskClass, RecommendedAction] = {
    RiskClass.DIRECT_PII: RecommendedAction.REVIEW_REQUIRED,
    RiskClass.INDIRECT_IDENTIFIER: RecommendedAction.KEEP,
    RiskClass.SENSITIVE_DATA: RecommendedAction.REVIEW_REQUIRED,
    RiskClass.LOW_RISK_ORG_DATA: RecommendedAction.KEEP,
    RiskClass.UNCERTAIN: RecommendedAction.KEEP,
}


class PolicyEngine:
    """Maps detections to risk and recommended action using config."""

    def __init__(self, config: Optional[PolicyConfig] = None):
        self.config = config or PolicyConfig()

    def _entity_to_risk(self, entity_type: EntityType) -> RiskClass:
        key = entity_type.value if isinstance(entity_type, EntityType) else str(entity_type)
        if key in self.config.allowlist_entities:
            return RiskClass.LOW_RISK_ORG_DATA
        if key in self.config.denylist_entities:
            return RiskClass.DIRECT_PII
        if key in self.config.entity_to_risk_map:
            return RiskClass(self.config.entity_to_risk_map[key])
        return _DEFAULT_ENTITY_RISK.get(entity_type, RiskClass.UNCERTAIN)

    def _risk_to_action(self, risk: RiskClass) -> RecommendedAction:
        key = risk.value
        if key in self.config.risk_to_action_map:
            return RecommendedAction(self.config.risk_to_action_map[key])
        mode = (self.config.mode or "balanced").lower()
        if mode == "strict":
            return _STRICT_ACTIONS.get(risk, RecommendedAction.REVIEW_REQUIRED)
        if mode == "permissive":
            return _PERMISSIVE_ACTIONS.get(risk, RecommendedAction.KEEP)
        return _BALANCED_ACTIONS.get(risk, RecommendedAction.REVIEW_REQUIRED)

    def _email_action_from_classification(self, email_class: Optional[EmailClassification]) -> Optional[RecommendedAction]:
        """
        Email classification → explicit policy döntés. Personal → mindig MASK.
        Role-based és organizational a config szerint: email_role_based_action, email_organizational_personal_action.
        """
        if email_class is None:
            return None
        allow_org = self.config.allow_organizational_emails
        allow_role = self.config.allow_role_based_emails
        action_str_org = (self.config.email_organizational_personal_action or "review").lower()
        action_str_role = (self.config.email_role_based_action or "keep").lower()

        if email_class == EmailClassification.PERSONAL_FREE_PROVIDER:
            return RecommendedAction.MASK
        if email_class == EmailClassification.ROLE_BASED_ORGANIZATIONAL:
            if not allow_role:
                return RecommendedAction.REVIEW_REQUIRED
            return {
                "keep": RecommendedAction.KEEP,
                "review": RecommendedAction.REVIEW_REQUIRED,
                "mask": RecommendedAction.MASK,
            }.get(action_str_role, RecommendedAction.KEEP)
        if email_class == EmailClassification.ORGANIZATIONAL_PERSONAL:
            if not allow_org:
                return RecommendedAction.MASK
            return {
                "keep": RecommendedAction.KEEP,
                "review": RecommendedAction.REVIEW_REQUIRED,
                "generalize": RecommendedAction.GENERALIZE,
                "mask": RecommendedAction.MASK,
            }.get(action_str_org, RecommendedAction.REVIEW_REQUIRED)
        return None

    def decide(self, detection: DetectionResult, index: int) -> PolicyDecision:
        """Produce policy decision for one detection."""
        entity_type = detection.entity_type
        risk = self._entity_to_risk(entity_type)

        action = self._risk_to_action(risk)
        allow_org = self.config.allow_organizational_emails
        allow_role = self.config.allow_role_based_emails

        # Email: intentional corporate vs personal handling
        if entity_type == EntityType.EMAIL_ADDRESS and isinstance(detection, EmailDetectionResult):
            email_action = self._email_action_from_classification(detection.email_classification)
            if email_action is not None:
                action = email_action

        # Dates / org / location
        if entity_type in (EntityType.DATE, EntityType.DATE_OF_BIRTH) and self.config.allow_dates:
            action = RecommendedAction.KEEP
        if entity_type == EntityType.UNKNOWN and risk == RiskClass.LOW_RISK_ORG_DATA:
            if "ORG" in str(detection.metadata) or detection.source_detector == "ner":
                if not self.config.allow_organization_names:
                    action = RecommendedAction.GENERALIZE
                else:
                    action = RecommendedAction.KEEP
            if not self.config.allow_locations and risk == RiskClass.INDIRECT_IDENTIFIER:
                action = RecommendedAction.GENERALIZE

        return PolicyDecision(
            detection_id=str(index),
            entity_type=entity_type,
            risk_class=risk,
            recommended_action=action,
            allow_organizational_email=allow_org,
            allow_role_based_email=allow_role,
            reason=None,
        )

    def decide_all(self, detections: List[DetectionResult]) -> List[PolicyDecision]:
        return [self.decide(d, i) for i, d in enumerate(detections)]
