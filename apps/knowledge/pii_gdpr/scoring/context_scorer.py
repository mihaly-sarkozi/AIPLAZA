"""
Context-based scoring: positive/negative keywords and proximity logic.
Composite score = pattern_score + context_score + document_type_score;
thresholds: 0.85+ mask, 0.60–0.84 review, below 0.60 ignore.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Set

from apps.knowledge.pii_gdpr.enums import EntityType, RecommendedAction

# Entity types that benefit from context rescoring (ambiguous patterns)
CONTEXT_SENSITIVE_ENTITY_TYPES: Set[EntityType] = {
    EntityType.VIN,
    EntityType.ENGINE_IDENTIFIER,
    EntityType.CHASSIS_IDENTIFIER,
    EntityType.VEHICLE_REGISTRATION,
    EntityType.CUSTOMER_ID,
    EntityType.IMEI,
    EntityType.MAC_ADDRESS,
    EntityType.IP_ADDRESS,
}

# Positive keywords (boost): presence in proximity increases confidence
POSITIVE_KEYWORDS: Dict[EntityType, List[str]] = {
    EntityType.VIN: [
        "vin", "vehicle identification", "chassis number", "alvázszám",
        "identificación del vehículo", "número de chasis",
    ],
    EntityType.ENGINE_IDENTIFIER: [
        "engine number", "motorszám", "número de motor", "motor number",
        "engine no", "motorkód",
    ],
    EntityType.CHASSIS_IDENTIFIER: [
        "chassis", "alvázszám", "chasis", "número de chasis", "chassis number",
    ],
    EntityType.VEHICLE_REGISTRATION: [
        "license plate", "rendszám", "matrícula", "plate", "registration",
        "number plate", "placa", "vehicle registration",
    ],
    EntityType.CUSTOMER_ID: [
        "customer", "ügyfél", "cliente", "client id", "customer id",
        "ugyfelszam", "número de cliente",
    ],
    EntityType.IMEI: ["imei", "device id", "mobile"],
    EntityType.MAC_ADDRESS: ["mac", "address", "ethernet", "wifi"],
    EntityType.IP_ADDRESS: ["ip", "address", "server", "host"],
}

# Negative keywords (penalty): presence in proximity decreases confidence (e.g. product/SKU)
NEGATIVE_KEYWORDS: Dict[EntityType, List[str]] = {
    EntityType.VIN: ["sku", "product", "cikkszám", "termék", "article", "item code"],
    EntityType.ENGINE_IDENTIFIER: ["sku", "product", "cikkszám", "termék", "article", "item", "factura", "invoice"],
    EntityType.CHASSIS_IDENTIFIER: ["sku", "product", "invoice", "factura"],
    EntityType.VEHICLE_REGISTRATION: ["sku", "product", "cikkszám", "termék", "article", "item code", "invoice"],
    EntityType.CUSTOMER_ID: [],
    EntityType.IMEI: [],
    EntityType.MAC_ADDRESS: [],
    EntityType.IP_ADDRESS: [],
}

# Default proximity window (chars before/after match)
DEFAULT_PROXIMITY_WINDOW = 80

# Thresholds
MASK_THRESHOLD = 0.85
REVIEW_THRESHOLD = 0.60
IGNORE_BELOW = 0.60

# Context score contribution (max boost/penalty)
CONTEXT_BOOST_MAX = 0.20
CONTEXT_PENALTY_MAX = -0.35
# When no positive keyword found for ambiguous types, apply this penalty so unlabeled matches get composite < MASK_THRESHOLD
NO_POSITIVE_CONTEXT_PENALTY = -0.20


def get_context_window(text: str, start: int, end: int, window: int = DEFAULT_PROXIMITY_WINDOW) -> str:
    """Return text in proximity of the span [start, end] for keyword search."""
    ctx_start = max(0, start - window)
    ctx_end = min(len(text), end + window)
    return text[ctx_start:ctx_end].lower()


def context_score(
    text: str,
    start: int,
    end: int,
    entity_type: EntityType,
    window: int = DEFAULT_PROXIMITY_WINDOW,
) -> float:
    """
    Compute context score in [-CONTEXT_PENALTY_MAX, +CONTEXT_BOOST_MAX].
    Positive keywords add up to CONTEXT_BOOST_MAX; negative subtract up to CONTEXT_PENALTY_MAX.
    """
    if entity_type not in POSITIVE_KEYWORDS and entity_type not in NEGATIVE_KEYWORDS:
        return 0.0
    ctx = get_context_window(text, start, end, window)
    score = 0.0
    positive_found = False
    for kw in POSITIVE_KEYWORDS.get(entity_type, []):
        if kw.lower() in ctx:
            score += 0.08
            positive_found = True
            if score >= CONTEXT_BOOST_MAX:
                break
    score = min(score, CONTEXT_BOOST_MAX)
    for kw in NEGATIVE_KEYWORDS.get(entity_type, []):
        if kw.lower() in ctx:
            score -= 0.12
            if score <= -CONTEXT_PENALTY_MAX:
                break
    score = max(score, -CONTEXT_PENALTY_MAX)
    # Ambiguous types: if no positive context, apply penalty so unlabeled (e.g. "Random code XYWZZZ...", "Product ABC-123") get composite < MASK
    if not positive_found and entity_type in (EntityType.VIN, EntityType.VEHICLE_REGISTRATION):
        score = min(score, NO_POSITIVE_CONTEXT_PENALTY)
    return score


def composite_score(
    pattern_score: float,
    context_score_val: float,
    document_type_score: float = 0.0,
) -> float:
    """Combine pattern + context + document_type; clamp to [0, 1]."""
    total = pattern_score + context_score_val + document_type_score
    return max(0.0, min(1.0, total))


def action_from_score(score: float) -> RecommendedAction:
    """Map composite score to action: 0.85+ mask, 0.60–0.84 review, below 0.60 ignore."""
    if score >= MASK_THRESHOLD:
        return RecommendedAction.MASK
    if score >= REVIEW_THRESHOLD:
        return RecommendedAction.REVIEW_REQUIRED
    return RecommendedAction.IGNORE


def should_ignore_by_score(score: float) -> bool:
    """True if score is below review threshold (detection should be dropped or marked ignore)."""
    return score < IGNORE_BELOW


class ContextScorer:
    """
    Reusable context scorer with configurable window and optional custom keyword maps.
    """

    def __init__(
        self,
        window: int = DEFAULT_PROXIMITY_WINDOW,
        positive_keywords: Optional[Dict[EntityType, List[str]]] = None,
        negative_keywords: Optional[Dict[EntityType, List[str]]] = None,
    ):
        self.window = window
        self.positive = positive_keywords or POSITIVE_KEYWORDS
        self.negative = negative_keywords or NEGATIVE_KEYWORDS

    def get_context_score(self, text: str, start: int, end: int, entity_type: EntityType) -> float:
        """Compute context score for a span."""
        if entity_type not in self.positive and entity_type not in self.negative:
            return 0.0
        ctx = get_context_window(text, start, end, self.window)
        score = 0.0
        positive_found = False
        for kw in self.positive.get(entity_type, []):
            if kw.lower() in ctx:
                score += 0.08
                positive_found = True
                if score >= CONTEXT_BOOST_MAX:
                    break
        score = min(score, CONTEXT_BOOST_MAX)
        for kw in self.negative.get(entity_type, []):
            if kw.lower() in ctx:
                score -= 0.12
                if score <= -CONTEXT_PENALTY_MAX:
                    break
        score = max(score, -CONTEXT_PENALTY_MAX)
        if not positive_found and entity_type in (EntityType.VIN, EntityType.VEHICLE_REGISTRATION):
            score = min(score, NO_POSITIVE_CONTEXT_PENALTY)
        return score

    def rescore_detection(
        self,
        text: str,
        pattern_score: float,
        start: int,
        end: int,
        entity_type: EntityType,
        document_type_score: float = 0.0,
    ) -> tuple[float, RecommendedAction]:
        """
        Return (composite_score, recommended_action).
        If entity_type is context-sensitive, apply context; else use pattern_score only.
        """
        if entity_type not in CONTEXT_SENSITIVE_ENTITY_TYPES:
            comp = composite_score(pattern_score, 0.0, document_type_score)
            return comp, action_from_score(comp)
        ctx = self.get_context_score(text, start, end, entity_type)
        comp = composite_score(pattern_score, ctx, document_type_score)
        return comp, action_from_score(comp)
