# apps/knowledge/pii_gdpr/detectors/base.py
"""
Base class for all PII detectors.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from apps.knowledge.pii_gdpr.models import DetectionResult


class BaseDetector(ABC):
    """Abstract base for detectors. Each detector returns a list of DetectionResult."""

    name: str = "base"

    @abstractmethod
    def detect(self, text: str, language: str = "en") -> List[DetectionResult]:
        """
        Run detection on text.
        :param text: Raw input text.
        :param language: Detected or provided language code (en, hu, es).
        :return: List of detections (may be empty).
        """
        pass

    def available(self) -> bool:
        """Return True if this detector can run (e.g. NER models loaded)."""
        return True
