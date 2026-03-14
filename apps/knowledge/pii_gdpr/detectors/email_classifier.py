# apps/knowledge/pii_gdpr/detectors/email_classifier.py
"""
Email classifier: personal/free vs organizational personal vs role-based organizational.
Returns classification and confidence for policy decisions.
"""
from __future__ import annotations

import re
from typing import List, Optional, Tuple

from apps.knowledge.pii_gdpr.enums import EmailClassification as EmailClass, EntityType, RiskClass, RecommendedAction
from apps.knowledge.pii_gdpr.models import EmailDetectionResult
from apps.knowledge.pii_gdpr.detectors.base import BaseDetector


# Well-known free/personal email domains
FREE_EMAIL_DOMAINS = frozenset({
    "gmail.com", "googlemail.com", "yahoo.com", "yahoo.co.uk", "hotmail.com", "outlook.com",
    "live.com", "msn.com", "icloud.com", "me.com", "aol.com", "protonmail.com", "zoho.com",
    "mail.com", "gmx.com", "gmx.net", "yandex.com", "seznam.cz", "freemail.hu", "t-online.de",
    "wp.pl", "o2.pl", "interia.pl", "orange.fr", "free.fr", "laposte.net", "web.de",
    "tutanota.com", "mailfence.com", "inbox.com", "fastmail.com", "rediffmail.com",
})

# Local-parts that typically indicate role/functional accounts
ROLE_KEYWORDS = frozenset({
    "info", "support", "help", "contact", "sales", "marketing", "admin", "office",
    "hr", "jobs", "careers", "press", "media", "news", "noreply", "no-reply",
    "feedback", "hello", "service", "customerservice", "contacto", "informacion",
    "info", "soporte", "ventas", "administracion", "ugyfelszolgalat", "kapcsolat",
})


def classify_email(email: str) -> Tuple[EmailClass, float]:
    """
    Classify a single email address.
    Returns (EmailClassification, confidence in [0, 1]).
    """
    if not email or "@" not in email:
        return EmailClass.UNKNOWN, 0.0
    local, _, domain = email.partition("@")
    domain_lower = domain.lower().strip()
    local_lower = local.lower().strip()

    # Free provider -> personal
    if domain_lower in FREE_EMAIL_DOMAINS:
        return EmailClass.PERSONAL_FREE_PROVIDER, 0.92

    # Role-like local part -> role-based organizational
    local_clean = re.sub(r"[._\-]", "", local_lower)
    if local_clean in ROLE_KEYWORDS:
        return EmailClass.ROLE_BASED_ORGANIZATIONAL, 0.88
    for kw in ROLE_KEYWORDS:
        if local_lower.startswith(kw) or local_lower.endswith(kw):
            return EmailClass.ROLE_BASED_ORGANIZATIONAL, 0.78

    # Otherwise organizational personal (name@company.domain)
    return EmailClass.ORGANIZATIONAL_PERSONAL, 0.75


class EmailClassifier(BaseDetector):
    """Detects emails and attaches classification (personal / org personal / role-based)."""

    name = "email_classifier"

    _EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")

    def detect(self, text: str, language: str = "en") -> List[EmailDetectionResult]:
        results: List[EmailDetectionResult] = []
        for m in self._EMAIL_PATTERN.finditer(text):
            email = m.group(0)
            classification, conf = classify_email(email)
            # Use confidence >= regex detector so merge keeps this (EmailDetectionResult) for policy
            results.append(
                EmailDetectionResult(
                    entity_type=EntityType.EMAIL_ADDRESS,
                    matched_text=email,
                    start=m.start(),
                    end=m.end(),
                    language=language,
                    source_detector=self.name,
                    confidence_score=0.96,
                    risk_level=RiskClass.DIRECT_PII,
                    recommended_action=RecommendedAction.MASK,
                    email_classification=classification,
                    email_classification_confidence=conf,
                )
            )
        return results
