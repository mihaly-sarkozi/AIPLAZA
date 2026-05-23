from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


KNOWLEDGE_QUALITY_REPORT_VERSION = "knowledge_quality_report_v0"


def _claims(profile: dict[str, Any]) -> list[dict[str, Any]]:
    return [dict(item) for item in profile.get("claims") or [] if isinstance(item, dict)]


def _claim_has_evidence(claim: dict[str, Any]) -> bool:
    evidence = claim.get("evidence") if isinstance(claim.get("evidence"), dict) else {}
    return bool(
        claim.get("claim_id")
        and (
            claim.get("sentence_id")
            or claim.get("sentence_ids")
            or evidence.get("sentence_id")
            or evidence.get("sentence_ids")
        )
        and (
            claim.get("source_id")
            or claim.get("source_ids")
            or evidence.get("source_id")
            or evidence.get("source_ids")
        )
    )


def _profile_has_evidence(profile: dict[str, Any]) -> bool:
    claims = _claims(profile)
    if claims:
        return any(_claim_has_evidence(claim) for claim in claims)
    evidence = profile.get("evidence") if isinstance(profile.get("evidence"), dict) else {}
    return bool(evidence.get("claim_ids") and evidence.get("sentence_ids") and (evidence.get("source_id") or evidence.get("source_ids")))


def _profile_has_conflict(profile: dict[str, Any]) -> bool:
    if profile.get("conflicting") or profile.get("profile_split"):
        return True
    for claim in _claims(profile):
        status = str(claim.get("claim_status") or claim.get("status") or "").strip()
        if status in {"disputed", "conflict"} or claim.get("conflict_marker"):
            return True
    for item in profile.get("tension_analyses") or []:
        if isinstance(item, dict) and bool(item.get("tension_detected")):
            return True
    return False


def _profile_is_fresh(profile: dict[str, Any]) -> bool:
    claims = _claims(profile)
    if not claims:
        return False
    return any(str(claim.get("claim_status") or claim.get("status") or "active") not in {"withdrawn", "weakened"} for claim in claims)


def _unknown_entity_type(profile: dict[str, Any]) -> bool:
    return str(profile.get("entity_type") or "").strip().lower() in {"", "unknown", "other"}


def _ratio(numerator: int | float, denominator: int | float) -> float:
    if not denominator:
        return 0.0
    return round(float(numerator) / float(denominator), 4)


class KnowledgeQualityReportV0:
    version = KNOWLEDGE_QUALITY_REPORT_VERSION

    def build(self, *, corpus_uuid: str, global_profiles: list[dict[str, Any]]) -> dict[str, Any]:
        profiles = [dict(item) for item in global_profiles if isinstance(item, dict)]
        total_profiles = len(profiles)
        claim_counts = [len(_claims(profile)) for profile in profiles]
        total_claims = sum(claim_counts)
        profiles_with_conflict = sum(1 for profile in profiles if _profile_has_conflict(profile))
        profiles_without_evidence = sum(1 for profile in profiles if not _profile_has_evidence(profile))
        profiles_with_fresh_claims = sum(1 for profile in profiles if _profile_is_fresh(profile))
        unknown_entity_type_count = sum(1 for profile in profiles if _unknown_entity_type(profile))
        evidenced_claim_count = sum(1 for profile in profiles for claim in _claims(profile) if _claim_has_evidence(claim))

        return {
            "corpus_uuid": corpus_uuid,
            "total_profiles": total_profiles,
            "profiles_with_conflict": profiles_with_conflict,
            "profiles_without_evidence": profiles_without_evidence,
            "avg_claims_per_profile": round(_ratio(total_claims, total_profiles), 4),
            "metrics": {
                "coverage": _ratio(total_profiles - profiles_without_evidence, total_profiles),
                "conflict_ratio": _ratio(profiles_with_conflict, total_profiles),
                "freshness": _ratio(profiles_with_fresh_claims, total_profiles),
                "evidence_density": _ratio(evidenced_claim_count, total_claims),
                "unknown_entity_type_ratio": _ratio(unknown_entity_type_count, total_profiles),
            },
            "counts": {
                "total_claims": total_claims,
                "evidenced_claims": evidenced_claim_count,
                "profiles_with_fresh_claims": profiles_with_fresh_claims,
                "unknown_entity_type_profiles": unknown_entity_type_count,
            },
            "profiles": [
                {
                    "profile_id": profile.get("profile_id"),
                    "entity_name": profile.get("entity_name"),
                    "entity_type": profile.get("entity_type"),
                    "claim_count": len(_claims(profile)),
                    "has_conflict": _profile_has_conflict(profile),
                    "has_evidence": _profile_has_evidence(profile),
                    "is_fresh": _profile_is_fresh(profile),
                    "unknown_entity_type": _unknown_entity_type(profile),
                }
                for profile in profiles
            ],
            "report_version": self.version,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }


__all__ = ["KNOWLEDGE_QUALITY_REPORT_VERSION", "KnowledgeQualityReportV0"]
