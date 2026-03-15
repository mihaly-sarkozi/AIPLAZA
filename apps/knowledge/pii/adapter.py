# apps/knowledge/pii/adapter.py
"""
Compatibility adapter: futtatja a pii_gdpr pipeline-t és legacy formátumra konvertál.
A detektálás source of truth a pii_gdpr; ez a modul csak (EntityType → legacy név) adapter.
Nincs legacy fallback; a pii.pipeline és pii_filter mindkettő ezen keresztül hívja a pii_gdpr-t.
"""
from __future__ import annotations

from typing import List, Tuple

from apps.knowledge.pii_gdpr.policy.legacy_mapping import get_legacy_name
from apps.knowledge.pii.sanitization import deduplicate_matches_longer_wins

# PiiMatch = (start, end, data_type: str, value: str)
PiiMatch = Tuple[int, int, str, str]


def _detect_via_gdpr(text: str, sensitivity: str) -> List[PiiMatch]:
    """
    Egyetlen policy engine: pii_gdpr. A sensitivity a PolicyConfig-ban van,
    a pipeline már csak az adott scope (weak/medium/strong) találatokat adja.
    """
    try:
        from apps.knowledge.pii_gdpr.pipeline.ingestion_pipeline import IngestionPipeline
        from apps.knowledge.pii_gdpr.models import AnalyzerConfig, PolicyConfig
    except ImportError as exc:
        raise RuntimeError("PII GDPR pipeline is unavailable") from exc

    pipeline = IngestionPipeline(
        analyzer_config=AnalyzerConfig(),
        policy_config=PolicyConfig(mode="balanced", sensitivity=sensitivity),
    )
    result = pipeline.run(text)
    raw = result.get("raw_detections") or []
    matches: List[PiiMatch] = []
    for d in raw:
        legacy_type = get_legacy_name(d.entity_type)
        matches.append((d.start, d.end, legacy_type, d.matched_text))

    return deduplicate_matches_longer_wins(matches)


def filter_pii_via_gdpr(text: str, sensitivity: str) -> List[PiiMatch]:
    """
    Futtatja a pii_gdpr pipeline-t és legacy formátumú találatokat ad vissza.
    Használja: pii_filter (elsődleges), pii.pipeline (delegálás). Fallback-et a hívó kezeli.
    """
    if not text or not text.strip():
        return []
    return _detect_via_gdpr(text, sensitivity)
