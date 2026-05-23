# backend/apps/knowledge/service/knowledge_feedback_service.py
# Owns knowledge feedback and source withdrawal effects on global profiles.

from __future__ import annotations

import re
import uuid as uuid_lib
from dataclasses import replace
from typing import Any

from apps.knowledge.errors import KnowledgeValidationError
from apps.knowledge.service.entity_key_normalization import canonicalize_entity_key
from apps.knowledge.service.facade_helpers import utcnow as _utcnow
from apps.knowledge.service.language_rules import fold_text


class KnowledgeFeedbackService:
    def __init__(
        self,
        *,
        source_store: Any,
        load_existing_global_profiles,
        log_step,
    ) -> None:
        self._source_store = source_store
        self._load_existing_global_profiles = load_existing_global_profiles
        self._log_step = log_step
        self._feedback_events: list[dict[str, Any]] = []
        self._source_withdrawal_events: list[dict[str, Any]] = []

    @staticmethod
    def feedback_key(value: Any) -> str:
        text = str(value or "").strip()
        return canonicalize_entity_key(text) or fold_text(text)

    @staticmethod
    def feedback_claim_text(claim: dict[str, Any]) -> str:
        return " ".join(
            part
            for part in [
                str(claim.get("claim_text") or claim.get("display_claim_text") or claim.get("canonical_claim_text") or "").strip(),
                str(claim.get("subject") or "").strip(),
                str(claim.get("predicate") or claim.get("predicate_text") or "").strip(),
                str(claim.get("object") or claim.get("object_text") or "").strip(),
            ]
            if part
        )

    @classmethod
    def feedback_claim_matches(cls, claim: dict[str, Any], claim_text: str) -> bool:
        target = fold_text(claim_text)
        if not target:
            return True
        haystack = fold_text(cls.feedback_claim_text(claim))
        if target in haystack or haystack in target:
            return True
        target_state = cls.feedback_state_object(claim_text)
        claim_object = str(claim.get("object") or claim.get("object_text") or "").strip().lower()
        claim_predicate = fold_text(claim.get("predicate") or claim.get("predicate_text"))
        return bool(target_state and claim_predicate == "active" and claim_object == target_state)

    @staticmethod
    def feedback_state_object(text: str) -> str | None:
        folded = fold_text(text)
        if re.search(r"\binactive\b|\binaktiv\b|\binaktív\b|\binactivo\b", folded):
            return "false"
        if re.search(r"\bactive\b|\baktiv\b|\baktív\b|\bactivo\b", folded):
            return "true"
        return None

    @classmethod
    def feedback_new_claim(cls, *, event_id: str, target_entity: str, claim_text: str) -> dict[str, Any]:
        text = str(claim_text or "").strip().rstrip(".")
        folded = fold_text(text)
        source_id = f"feedback-source:{event_id}"
        sentence_id = f"feedback-sentence:{event_id}"
        claim_id = f"feedback-claim:{event_id}"
        state_object = cls.feedback_state_object(text)
        if state_object is not None:
            return {
                "claim_id": claim_id,
                "subject": target_entity,
                "claim_text": text,
                "predicate": "active",
                "predicate_text": "active",
                "object": state_object,
                "object_text": state_object,
                "claim_type": "state",
                "claim_group": "state",
                "status": "active",
                "claim_status": "active",
                "time_mode": "current",
                "time_dominant": "current",
                "time_values": [],
                "sentence_ids": [sentence_id],
                "sentence_text": text + ".",
                "source_ids": [source_id],
                "feedback_weight": 1.0,
                "evidence": {"source_id": source_id, "source_ids": [source_id], "sentence_ids": [sentence_id]},
            }
        rule_match = re.search(r"\b(must|should|required to|kell|kötelező|debe)\b\s+(.+)$", text, flags=re.IGNORECASE)
        if rule_match:
            predicate = rule_match.group(1).strip()
            obj = rule_match.group(2).strip()
            return {
                "claim_id": claim_id,
                "subject": target_entity,
                "claim_text": text,
                "predicate": predicate,
                "predicate_text": predicate,
                "object": obj,
                "object_text": obj,
                "claim_type": "rule_procedure",
                "claim_group": "rule",
                "status": "active",
                "claim_status": "active",
                "time_mode": "timeless",
                "sentence_ids": [sentence_id],
                "sentence_text": text + ".",
                "source_ids": [source_id],
                "feedback_weight": 1.0,
                "evidence": {"source_id": source_id, "source_ids": [source_id], "sentence_ids": [sentence_id]},
            }
        relation_match = re.search(r"\b(uses|use|integrates with|integrates|használ|utiliza|usa)\b\s+(.+)$", text, flags=re.IGNORECASE)
        if relation_match:
            predicate = relation_match.group(1).strip()
            obj = relation_match.group(2).strip()
            return {
                "claim_id": claim_id,
                "subject": target_entity,
                "claim_text": text,
                "predicate": predicate,
                "predicate_text": predicate,
                "object": obj,
                "object_text": obj,
                "claim_group": "relation",
                "status": "active",
                "claim_status": "active",
                "time_mode": "timeless",
                "sentence_ids": [sentence_id],
                "sentence_text": text + ".",
                "source_ids": [source_id],
                "feedback_weight": 1.0,
                "evidence": {"source_id": source_id, "source_ids": [source_id], "sentence_ids": [sentence_id]},
            }
        obj = text
        if cls.feedback_key(target_entity) and folded.startswith(cls.feedback_key(target_entity)):
            obj = text[len(target_entity):].strip()
        return {
            "claim_id": claim_id,
            "subject": target_entity,
            "claim_text": text,
            "predicate": "states",
            "predicate_text": "states",
            "object": obj,
            "object_text": obj,
            "claim_group": "descriptor",
            "status": "active",
            "claim_status": "active",
            "time_mode": "timeless",
            "sentence_ids": [sentence_id],
            "sentence_text": text + ".",
            "source_ids": [source_id],
            "feedback_weight": 1.0,
            "evidence": {"source_id": source_id, "source_ids": [source_id], "sentence_ids": [sentence_id]},
        }

    @staticmethod
    def weaken_feedback_claim(claim: dict[str, Any]) -> dict[str, Any]:
        updated = dict(claim)
        updated["claim_status"] = "weakened"
        updated["status"] = "weakened"
        updated["feedback_weight"] = max(0.0, float(updated.get("feedback_weight") or 1.0) - 0.5)
        return updated

    @staticmethod
    def reinforce_feedback_claim(claim: dict[str, Any]) -> dict[str, Any]:
        updated = dict(claim)
        updated["claim_status"] = "active"
        if str(updated.get("status") or "").strip().lower() in {"weakened", "disputed"}:
            updated["status"] = "active"
        updated["feedback_weight"] = min(2.0, float(updated.get("feedback_weight") or 1.0) + 0.25)
        return updated

    def apply_feedback_to_global_profiles(
        self,
        *,
        corpus_uuid: str,
        global_profiles: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        events = [event for event in self._feedback_events if event.get("corpus_uuid") == corpus_uuid]
        if not events:
            return global_profiles, []
        profiles = [dict(profile, claims=[dict(claim) for claim in profile.get("claims") or [] if isinstance(claim, dict)]) for profile in global_profiles]
        applied_events: list[dict[str, Any]] = []
        for event in events:
            target_key = self.feedback_key(event.get("target_entity"))
            if not target_key:
                continue
            for profile in profiles:
                profile_key = self.feedback_key(profile.get("canonical_key") or profile.get("entity_name"))
                if profile_key != target_key:
                    continue
                affected: list[str] = []
                claims = []
                for claim in profile.get("claims") or []:
                    claim_id = str(claim.get("claim_id") or "").strip()
                    if self.feedback_claim_matches(claim, str(event.get("claim_text") or "")):
                        affected.append(claim_id)
                        if event.get("feedback_type") in {"incorrect", "replace"}:
                            claim = self.weaken_feedback_claim(claim)
                        elif event.get("feedback_type") == "correct":
                            claim = self.reinforce_feedback_claim(claim)
                    claims.append(claim)
                new_claim_ids: list[str] = []
                if event.get("feedback_type") == "replace" and event.get("optional_new_claim"):
                    new_claim = self.feedback_new_claim(
                        event_id=str(event.get("feedback_event_id")),
                        target_entity=str(event.get("target_entity") or profile.get("entity_name") or ""),
                        claim_text=str(event.get("optional_new_claim") or ""),
                    )
                    claims.append(new_claim)
                    new_claim_ids.append(str(new_claim.get("claim_id") or ""))
                profile["claims"] = claims
                applied = {**event, "affected_claim_ids": affected, "new_claim_ids": new_claim_ids}
                applied_events.append(applied)
        return profiles, applied_events

    def apply(
        self,
        *,
        tenant: str,
        corpus_uuid: str,
        target_entity: str,
        claim_text: str,
        feedback_type: str,
        optional_new_claim: str | None = None,
        user_input: str | None = None,
        user_id: int | None = None,
    ) -> dict[str, Any]:
        normalized_type = str(feedback_type or "").strip().lower()
        if normalized_type not in {"correct", "incorrect", "replace"}:
            raise KnowledgeValidationError("feedback_type must be one of: correct, incorrect, replace.")
        if normalized_type == "replace" and not str(optional_new_claim or "").strip():
            raise KnowledgeValidationError("optional_new_claim is required for replace feedback.")
        event = {
            "feedback_event_id": str(uuid_lib.uuid4()),
            "tenant": tenant,
            "corpus_uuid": corpus_uuid,
            "target_entity": str(target_entity or "").strip(),
            "claim_text": str(claim_text or "").strip(),
            "feedback_type": normalized_type,
            "optional_new_claim": str(optional_new_claim or "").strip() or None,
            "user_input": user_input or str(optional_new_claim or claim_text or "").strip(),
            "user_id": user_id,
            "created_at": _utcnow().isoformat(),
            "affected_claim_ids": [],
            "new_claim_ids": [],
        }
        self._feedback_events.append(event)
        global_profiles = self._load_existing_global_profiles(corpus_uuid=corpus_uuid, exclude_interpretation_run_id=None)
        _, applied_events = self.apply_feedback_to_global_profiles(corpus_uuid=corpus_uuid, global_profiles=global_profiles)
        applied = next((item for item in reversed(applied_events) if item.get("feedback_event_id") == event["feedback_event_id"]), event)
        self._log_step("knowledge.feedback.apply", status="ok", tenant=tenant, corpus_uuid=corpus_uuid, feedback_type=normalized_type)
        return {"feedback_event": applied}

    @staticmethod
    def claim_source_ids_for_withdrawal(claim: dict[str, Any]) -> list[str]:
        evidence = claim.get("evidence") if isinstance(claim.get("evidence"), dict) else {}
        ids: list[str] = []
        for value in [
            claim.get("source_id"),
            evidence.get("source_id"),
            *(claim.get("source_ids") or []),
            *(evidence.get("source_ids") or []),
        ]:
            text = str(value or "").strip()
            if text and text not in ids:
                ids.append(text)
        return ids

    @staticmethod
    def withdraw_claim(claim: dict[str, Any]) -> dict[str, Any]:
        updated = dict(claim)
        updated["claim_status"] = "withdrawn"
        updated["status"] = "withdrawn"
        updated["feedback_weight"] = 0.0
        return updated

    def apply_source_withdrawals_to_global_profiles(
        self,
        *,
        corpus_uuid: str,
        global_profiles: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        events = [event for event in self._source_withdrawal_events if event.get("corpus_uuid") == corpus_uuid]
        if not events:
            return global_profiles, []
        profiles = [dict(profile, claims=[dict(claim) for claim in profile.get("claims") or [] if isinstance(claim, dict)]) for profile in global_profiles]
        applied_events: list[dict[str, Any]] = []
        for event in events:
            source_id = str(event.get("source_id") or "").strip()
            if not source_id:
                continue
            affected_claim_ids: list[str] = []
            affected_profile_ids: list[str] = []
            for profile in profiles:
                claims: list[dict[str, Any]] = []
                profile_touched = False
                for claim in profile.get("claims") or []:
                    if source_id in self.claim_source_ids_for_withdrawal(claim):
                        claim = self.withdraw_claim(claim)
                        claim_id = str(claim.get("claim_id") or "").strip()
                        if claim_id and claim_id not in affected_claim_ids:
                            affected_claim_ids.append(claim_id)
                        profile_touched = True
                    claims.append(claim)
                if profile_touched:
                    profile_id = str(profile.get("profile_id") or "").strip()
                    if profile_id and profile_id not in affected_profile_ids:
                        affected_profile_ids.append(profile_id)
                profile["claims"] = claims
            applied_events.append(
                {
                    **event,
                    "affected_claim_ids": affected_claim_ids,
                    "affected_profile_ids": affected_profile_ids,
                }
            )
        return profiles, applied_events

    def withdraw_source(
        self,
        *,
        tenant: str,
        corpus_uuid: str,
        source_id: str,
        user_input: str | None = None,
        user_id: int | None = None,
    ) -> dict[str, Any]:
        normalized_source_id = str(source_id or "").strip()
        if not normalized_source_id:
            raise KnowledgeValidationError("source_id is required.")
        event = {
            "source_withdrawal_event_id": str(uuid_lib.uuid4()),
            "tenant": tenant,
            "corpus_uuid": corpus_uuid,
            "source_id": normalized_source_id,
            "user_input": user_input or f"withdraw_source({normalized_source_id})",
            "user_id": user_id,
            "created_at": _utcnow().isoformat(),
            "affected_claim_ids": [],
            "affected_profile_ids": [],
        }
        self._source_withdrawal_events.append(event)
        source = self._source_store.get(normalized_source_id)
        if source is not None:
            metadata = dict(source.metadata or {})
            metadata.update(
                {
                    "withdrawn": True,
                    "withdrawn_at": event["created_at"],
                    "withdrawn_by": user_id,
                }
            )
            self._source_store.update(replace(source, metadata=metadata))
        global_profiles = self._load_existing_global_profiles(corpus_uuid=corpus_uuid, exclude_interpretation_run_id=None)
        _, applied_events = self.apply_source_withdrawals_to_global_profiles(corpus_uuid=corpus_uuid, global_profiles=global_profiles)
        applied = next((item for item in reversed(applied_events) if item.get("source_withdrawal_event_id") == event["source_withdrawal_event_id"]), event)
        self._log_step("knowledge.source.withdraw", status="ok", tenant=tenant, corpus_uuid=corpus_uuid, source_id=normalized_source_id)
        return {"source_withdrawal_event": applied}


__all__ = ["KnowledgeFeedbackService"]
