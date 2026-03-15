from __future__ import annotations

import json
import uuid as uuid_lib
import hashlib
import logging
import re
from datetime import UTC, datetime
from collections import Counter
from time import perf_counter
from typing import List, Optional, Any, TYPE_CHECKING
from config.settings import settings
from apps.knowledge.ports.repositories import KnowledgeBaseRepositoryPort, KbPermissionItem
from apps.knowledge.domain.kb import KnowledgeBase
from apps.knowledge.application.pii_filter import (
    filter_pii,
    apply_pii_replacements_with_decisions,
    PiiConfirmationRequiredError,
)
from apps.knowledge.infrastructure.db.models import (
    PERSONAL_DATA_MODE_NO,
    PERSONAL_DATA_MODE_CONFIRM,
    PERSONAL_DATA_MODE_ALLOWED,
    PERSONAL_DATA_MODE_DISABLED,
)
from apps.knowledge.application.file_ingest import (
    extract_file,
    ExtractedFileResult,
    FileMetadata,
    STATUS_EMPTY,
    STATUS_SCANNED_REVIEW_REQUIRED,
)
from apps.knowledge.domain.pii_review import (
    build_pii_review_payload,
    build_pii_review_matches,
    PiiReviewDecision,
)
from apps.knowledge.application.context_builder import KnowledgeContextBuilder
from apps.knowledge.application.reranker import compute_time_overlap_score
from apps.knowledge.application.scoring import (
    decay_strength,
    reinforce_strength,
    compute_delta_days,
    compute_current_strength,
    alpha_for_event,
    normalize_event_type,
    determine_assertion_status,
)

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from apps.core.qdrant.qdrant_wrapper import QdrantClientWrapper


def _metadata_for_response(meta: FileMetadata) -> dict[str, Any]:
    return {
        "filename": meta.filename,
        "author": meta.author,
        "creator": meta.creator,
        "modified_by": meta.modified_by,
    }


def _user_repo_list_all(user_repo: Any) -> List[Any]:
    if user_repo is None:
        return []
    return user_repo.list_all()


def _norm(s: str) -> str:
    return (s or "").strip().lower()


def _qhash(s: str) -> str:
    return hashlib.sha256((s or "").encode("utf-8")).hexdigest()[:16]


def _normalize_place_key(value: str) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _relation_type_proximity_factor(relation_type: str | None) -> float:
    rel = str(relation_type or "").strip().upper()
    return {
        "SUPPORTS": 1.0,
        "REFINES": 0.95,
        "GENERALIZES": 0.82,
        "CONTRADICTS": 0.72,
        "TEMPORALLY_SPLITS": 0.84,
        "TEMPORALLY_OVERLAPS": 0.78,
        "SAME_SUBJECT": 0.72,
        "SAME_OBJECT": 0.68,
        "SAME_PREDICATE": 0.62,
        "SAME_PLACE": 0.60,
        "SAME_SOURCE_POINT": 0.45,
    }.get(rel, 0.62)


def _valid_time_from_value(row: dict[str, Any]) -> Any:
    return row.get("valid_time_from") or row.get("time_from")


def _valid_time_to_value(row: dict[str, Any]) -> Any:
    return row.get("valid_time_to") or row.get("time_to")


def _iso_or_none(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    text = str(value).strip()
    return text or None


def _dedupe_keep_order(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        key = str(value or "").strip()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(key)
    return out


def _time_semantics_debug(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "valid_time": {
            "from": _iso_or_none(_valid_time_from_value(row)),
            "to": _iso_or_none(_valid_time_to_value(row)),
        },
        "source_time": _iso_or_none(row.get("source_time")),
        "ingest_time": _iso_or_none(row.get("ingest_time")),
    }


def _row_place_keys(row: dict[str, Any]) -> list[str]:
    keys = [
        _normalize_place_key(x)
        for x in (row.get("place_keys") or [])
        if _normalize_place_key(x)
    ]
    single_key = _normalize_place_key(str(row.get("place_key") or ""))
    if single_key:
        keys.append(single_key)
    return _dedupe_keep_order(keys)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _sanitize_debug_text(value: Any) -> str:
    text = str(value or "")
    if not text:
        return ""
    text = re.sub(r"(?i)\b[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}\b", "[redacted_email]", text)
    text = re.sub(r"\b(?:\+?\d[\d\s().-]{6,}\d)\b", "[redacted_phone]", text)
    text = re.sub(r"\b\d{6,}\b", "[redacted_number]", text)
    return text[:400] + ("..." if len(text) > 400 else "")


def _sanitize_debug_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _sanitize_debug_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_sanitize_debug_value(v) for v in value]
    if isinstance(value, tuple):
        return [_sanitize_debug_value(v) for v in value]
    if isinstance(value, str):
        return _sanitize_debug_text(value)
    return value


def _assertion_context_rank(row: dict[str, Any]) -> tuple:
    return (
        -_safe_float(row.get("entity_match")),
        -_safe_float(row.get("time_match")),
        -_safe_float(row.get("place_match")),
        -_safe_float(row.get("relation_confidence")),
        -_safe_float(row.get("graph_proximity")),
        -_safe_float(row.get("strength")),
        -_safe_float(row.get("confidence")),
        str(_valid_time_from_value(row) or _valid_time_to_value(row) or ""),
        str(row.get("id") or ""),
    )


def _evidence_context_rank(row: dict[str, Any], primary_assertion_ids: set[int], supporting_assertion_ids: set[int]) -> tuple:
    assertion_id = int(row.get("assertion_id") or 0)
    layer_boost = 2 if assertion_id in primary_assertion_ids else (1 if assertion_id in supporting_assertion_ids else 0)
    return (
        -layer_boost,
        -_safe_float(row.get("evidence_weight")),
        -_safe_float(row.get("evidence_confidence")),
        -len(row.get("entity_ids") or []),
        -len(row.get("place_keys") or []),
        str(_valid_time_from_value(row) or _valid_time_to_value(row) or ""),
        str(row.get("sentence_id") or ""),
    )


def _chunk_context_rank(row: dict[str, Any], primary_assertion_ids: set[int], supporting_assertion_ids: set[int]) -> tuple:
    linked_ids = {int(x) for x in (row.get("assertion_ids") or []) if isinstance(x, int)}
    primary_links = len(linked_ids.intersection(primary_assertion_ids))
    supporting_links = len(linked_ids.intersection(supporting_assertion_ids))
    return (
        -primary_links,
        -supporting_links,
        -len(linked_ids),
        -len(row.get("entity_ids") or []),
        -len(row.get("place_keys") or []),
        str(_valid_time_from_value(row) or _valid_time_to_value(row) or ""),
        str(row.get("chunk_id") or row.get("id") or ""),
    )


def _compose_query_representation(question: str, parsed_query: dict[str, Any]) -> dict[str, str]:
    entity_terms = _dedupe_keep_order([str(x).strip() for x in (parsed_query.get("entity_candidates") or []) if str(x).strip()])
    place_terms = _dedupe_keep_order([_normalize_place_key(str(x)) for x in (parsed_query.get("place_candidates") or []) if _normalize_place_key(str(x))])
    time_terms = _dedupe_keep_order([str(x).strip() for x in (parsed_query.get("time_candidates") or []) if str(x).strip()])
    predicate_terms = _dedupe_keep_order([str(x).strip().lower() for x in (parsed_query.get("predicate_candidates") or []) if str(x).strip()])
    attribute_terms = _dedupe_keep_order([str(x).strip().lower() for x in (parsed_query.get("attribute_candidates") or []) if str(x).strip()])
    relation_terms = _dedupe_keep_order([str(x).strip().lower() for x in (parsed_query.get("relation_candidates") or []) if str(x).strip()])
    focus_terms = _dedupe_keep_order([str(x).strip().lower() for x in (parsed_query.get("lexical_focus_terms") or []) if str(x).strip()])
    raw_query = str(parsed_query.get("raw_query") or question or "").strip()
    normalized_parts = [
        raw_query,
        " ".join(entity_terms),
        " ".join(place_terms),
        " ".join(time_terms),
        " ".join(predicate_terms),
        " ".join(attribute_terms),
        " ".join(relation_terms),
    ]
    lexical_parts = normalized_parts + [" ".join(focus_terms)]
    normalized_query_text = " ".join(part for part in normalized_parts if part).strip()
    lexical_query_text = " ".join(part for part in lexical_parts if part).strip()
    return {
        "normalized_query_text": normalized_query_text or raw_query,
        "lexical_query_text": lexical_query_text or normalized_query_text or raw_query,
        "query_embedding_text": lexical_query_text or normalized_query_text or raw_query,
    }


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _normalize_score_range(value: float, min_value: float, max_value: float) -> float:
    if max_value <= min_value:
        return _clamp01(value)
    return _clamp01((value - min_value) / (max_value - min_value))


def _parse_assertion_id(value: Any) -> int | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    if raw.isdigit():
        return int(raw)
    if raw.startswith("assertion-") and raw.split("-", 1)[1].isdigit():
        return int(raw.split("-", 1)[1])
    return None


def _utcnow_naive() -> datetime:
    """UTC now timezone-naive formában."""
    return datetime.now(UTC).replace(tzinfo=None)


class KnowledgeBaseService:

    def __init__(
        self,
        repo: KnowledgeBaseRepositoryPort,
        qdrant_service: "QdrantClientWrapper",
        user_repo: Any = None,
        indexing_pipeline: Any = None,
    ) -> None:
        self.repo = repo
        self.qdrant = qdrant_service
        self.user_repo = user_repo
        self.indexing_pipeline = indexing_pipeline
        self.context_builder = KnowledgeContextBuilder()

    def _enqueue_vector_outbox(
        self,
        kb_id: int,
        operation_type: str,
        payload: dict,
        source_point_id: Optional[str] = None,
    ) -> None:
        """Qdrant eltérés esetén outbox retry feladat sorba állítása."""
        try:
            self.repo.enqueue_vector_outbox(
                kb_id=kb_id,
                operation_type=operation_type,
                payload=payload,
                source_point_id=source_point_id,
            )
        except Exception:
            # Outbox írási hiba esetén sem dobunk tovább itt; audit/monitor oldalon látszódik.
            pass

    def list_all(
        self,
        current_user_id: Optional[int] = None,
        current_user_role: Optional[str] = None,
    ) -> List[KnowledgeBase]:
        """Owner mindent lát; admin csak a kezelhető (train) KB-kat; user csak use/train jogosat."""
        if current_user_id is None:
            return []
        all_kbs = self.repo.list_all()
        if current_user_role == "owner":
            return all_kbs
        if current_user_role == "admin":
            allowed_ids = set(self.repo.get_kb_ids_with_permission(current_user_id, "train"))
        else:
            allowed_ids = set(self.repo.get_kb_ids_with_permission(current_user_id, "use"))
        return [kb for kb in all_kbs if kb.id is not None and kb.id in allowed_ids]

    def list_all_unfiltered(self) -> List[KnowledgeBase]:
        """Összes knowledge base (admin listához)."""
        return self.repo.list_all()

    def get_trainable_kb_ids(self, user_id: int, user_role: Optional[str]) -> set[int]:
        """Azon KB id-k, amelyeket a user taníthat (owner: minden)."""
        if user_role == "owner":
            return {
                kb.id for kb in self.repo.list_all() if kb.id is not None
            }
        return set(self.repo.get_kb_ids_with_permission(user_id, "train"))

    def create(
        self,
        name: str,
        description: str | None = None,
        permissions: Optional[List[KbPermissionItem]] = None,
        current_user_id: Optional[int] = None,
    ) -> KnowledgeBase:
        """Új knowledge base létrehozása; opcionálisan jogosultságokkal. A létrehozó mindig train jogot kap."""
        if self.repo.get_by_name(name):
            raise ValueError("KB name already exists")

        kb_uuid = str(uuid_lib.uuid4())
        collection_name = f"kb_{kb_uuid}"

        self.qdrant.create_collection(collection_name)

        kb = KnowledgeBase(
            id=None,
            uuid=kb_uuid,
            name=name,
            description=description,
            qdrant_collection_name=collection_name,
            created_at=None,
            updated_at=None
        )

        created = self.repo.create(kb)
        perms = [(uid, p) for uid, p in (permissions or []) if p and p != "none"]
        if current_user_id is not None and not any(uid == current_user_id for uid, _ in perms):
            perms.append((current_user_id, "train"))
        self.repo.set_permissions(created.uuid, perms)
        return created

    def update(
        self,
        uuid: str,
        name: str,
        description: str,
        personal_data_mode: Optional[str] = None,
    ) -> KnowledgeBase:
        """Knowledge base frissítése (név, leírás, személyes adatok beállításai)."""
        kb = self.repo.get_by_uuid(uuid)
        if not kb:
            raise ValueError("KB not found")

        kb.name = name
        kb.description = description
        if personal_data_mode is not None:
            kb.personal_data_mode = personal_data_mode
        return self.repo.update(kb)

    def delete(self, uuid: str, confirm_name: str | None = None) -> None:
        """Knowledge base törlése."""
        kb = self.repo.get_by_uuid(uuid)
        if not kb:
            raise ValueError("KB not found")

        # Ha confirm_name van megadva, ellenőrizzük
        if confirm_name and confirm_name != kb.name:
            raise ValueError("Confirmation name does not match")

        self.qdrant.delete_collection(kb.qdrant_collection_name)
        self.repo.delete(uuid)

    def get_permissions_with_users(self, kb_uuid: str) -> List[dict]:
        """Jogosultságok listája user adatokkal: { user_id, email, name, permission }."""
        perm_list = self.repo.list_permissions(kb_uuid)
        perm_by_user = {uid: p for uid, p in perm_list}
        users = _user_repo_list_all(self.user_repo)
        result = []
        for u in users:
            if getattr(u, "id", None) is None:
                continue
            result.append({
                "user_id": u.id,
                "email": getattr(u, "email", "") or "",
                "name": getattr(u, "name", None),
                "permission": perm_by_user.get(u.id, "none"),
                "role": getattr(u, "role", "user"),
            })
        return result

    def get_permissions_with_users_batch(self, kb_uuids: List[str]) -> dict[str, List[dict]]:
        """Jogosultságok több tudástárra egyben, user adatokkal."""
        if not kb_uuids:
            return {}
        users = _user_repo_list_all(self.user_repo)
        perms_by_kb = self.repo.list_permissions_batch(kb_uuids)
        out: dict[str, List[dict]] = {}
        for kb_uuid in kb_uuids:
            perm_by_user = {uid: p for uid, p in (perms_by_kb.get(kb_uuid) or [])}
            rows = []
            for u in users:
                if getattr(u, "id", None) is None:
                    continue
                rows.append({
                    "user_id": u.id,
                    "email": getattr(u, "email", "") or "",
                    "name": getattr(u, "name", None),
                    "permission": perm_by_user.get(u.id, "none"),
                    "role": getattr(u, "role", "user"),
                })
            out[kb_uuid] = rows
        return out

    def set_permissions(
        self, kb_uuid: str, permissions: List[KbPermissionItem], current_user_id: Optional[int] = None
    ) -> None:
        """Jogosultságok beállítása. A current_user saját jogát egyáltalán nem módosítjuk."""
        if current_user_id is not None:
            existing = self.repo.list_permissions(kb_uuid)
            existing_self = next((p for uid, p in existing if uid == current_user_id), "train")
            perms = []
            for uid, perm in permissions:
                if uid == current_user_id:
                    continue
                if perm and perm != "none":
                    perms.append((uid, perm))
            perms.append((current_user_id, existing_self if existing_self else "train"))
            self.repo.set_permissions(kb_uuid, perms)
        else:
            self.repo.set_permissions(
                kb_uuid, [(uid, p) for uid, p in permissions if p and p != "none"]
            )

    def user_can_use(self, kb_uuid: str, user_id: int, user_role: Optional[str]) -> bool:
        """Owner mindent használhat; különben csak ha van use/train joga."""
        if user_role == "owner":
            return True
        kb = self.repo.get_by_uuid(kb_uuid)
        if not kb or kb.id is None:
            return False
        allowed = self.repo.get_kb_ids_with_permission(user_id, "use")
        return kb.id in allowed

    def user_can_train(self, kb_uuid: str, user_id: int, user_role: Optional[str]) -> bool:
        """Owner mindent taníthat és kezelhet; különben csak ha van train joga."""
        if user_role == "owner":
            return True
        kb = self.repo.get_by_uuid(kb_uuid)
        if not kb or kb.id is None:
            return False
        allowed = self.repo.get_kb_ids_with_permission(user_id, "train")
        return kb.id in allowed

    # ------------------------------------------------------------
    #  ADD BLOCK – TANÍTÁS (egy tanítás = egy sor a naplóban, teljes tartalommal)
    # ------------------------------------------------------------
    async def add_block(
        self,
        uuid: str,
        title: str,
        content: str,
        idempotency_key: Optional[str] = None,
        current_user_id: Optional[int] = None,
        confirm_pii: bool = False,
        pii_review_decision: Optional[str] = None,
        pii_decisions: Optional[List[dict]] = None,
        sanitize_mode: Optional[str] = None,
    ) -> dict[str, Any]:
        """Tanítási tartalom mentése; személyes adatok szűrése a KB beállítások szerint."""
        kb = self.repo.get_by_uuid(uuid)
        if not kb or kb.id is None:
            raise ValueError("KB not found")
        if not content or not content.strip():
            raise ValueError("Nincs feltöltött szöveg vagy tartalom.")
        idem_key = (idempotency_key or "").strip() or None
        if idem_key:
            existing = self.repo.get_training_log_by_idempotency_key(kb.id, idem_key)
            if existing:
                return {
                    "status": "ok",
                    "idempotent_replay": True,
                    "point_id": existing.get("point_id"),
                    "masked": False,
                    "pii_replaced_with_dots": False,
                    "indexing": None,
                }

        raw = content.strip()
        mode = getattr(kb, "personal_data_mode", None) or PERSONAL_DATA_MODE_NO
        sensitivity = getattr(kb, "personal_data_sensitivity", None) or "medium"
        if mode == PERSONAL_DATA_MODE_DISABLED:
            matches = []
        else:
            matches = filter_pii(raw, sensitivity)

        # Soronkénti döntések (with_confirmation): pii_decisions = [{index, decision}, ...]
        has_pii_decisions = (
            pii_decisions is not None
            and isinstance(pii_decisions, list)
            and len(pii_decisions) >= len(matches)
        )
        if has_pii_decisions:
            # index szerint rendezett decisions lista
            dec_by_idx = {int(d.get("index", -1)): str(d.get("decision", "mask")) for d in pii_decisions if isinstance(d, dict)}
            decisions_list = [dec_by_idx.get(i, "mask") for i in range(len(matches))]
        else:
            decisions_list = None

        # User confirmed but chose to reject upload (régi flow, ha nincs pii_decisions)
        if matches and confirm_pii and not decisions_list and pii_review_decision == PiiReviewDecision.REJECT_UPLOAD.value:
            return {"status": "rejected", "message": "A feltöltés elutasítva."}

        # with_confirmation: vagy pii_decisions (soronkénti), vagy régi flow (pii_review_decision=continue_sanitized/mask_all)
        legacy_confirm = (
            confirm_pii
            and not decisions_list
            and pii_review_decision
            and pii_review_decision in (
                PiiReviewDecision.CONTINUE_SANITIZED.value,
                PiiReviewDecision.MASK_ALL.value,
            )
        )
        user_confirmed = decisions_list is not None or legacy_confirm

        if matches:
            if mode == PERSONAL_DATA_MODE_NO:
                # Automatikus törlés: cseréljük "..."-ra és tároljuk
                pass  # nem dobunk hibát, lejjebb cseréljük
            elif mode == PERSONAL_DATA_MODE_CONFIRM and not user_confirmed:
                detected_types, counts, snippets = build_pii_review_payload(matches)
                review_matches = build_pii_review_matches(raw, matches)
                raise PiiConfirmationRequiredError(
                    detected_types,
                    counts=counts,
                    snippets=snippets,
                    matches=review_matches,
                )

        display_title = (title or "").strip()
        point_id = str(uuid_lib.uuid4())

        masked = False
        if matches:
            if mode == PERSONAL_DATA_MODE_DISABLED:
                content_to_store = raw
            else:
                # GDPR ellenőrzés aktív: minden talált PII mindig maszkolva mentődik.
                ref_ids = [
                    self.repo.add_personal_data(kb.id, point_id, m[2], m[3])
                    for m in matches
                ]
                # A felhasználói keep/delete döntéseket biztonsági okból felülírjuk maszkolásra.
                forced_mask_decisions = ["mask"] * len(matches)
                content_to_store, _ = apply_pii_replacements_with_decisions(
                    raw, matches, forced_mask_decisions, ref_id_by_index=ref_ids
                )
                masked = True
        else:
            content_to_store = raw

        user_display = ""
        if current_user_id and self.user_repo:
            u = self.user_repo.get_by_id(current_user_id)
            if u:
                user_display = (getattr(u, "name", None) or "").strip() or getattr(u, "email", "") or ""
        decision = None
        if matches and confirm_pii:
            decision = pii_review_decision
        if decisions_list:
            decision = json.dumps([{"index": i, "decision": d} for i, d in enumerate(decisions_list)])
        self.repo.add_training_log(
            kb_id=kb.id,
            point_id=point_id,
            user_id=current_user_id,
            user_display=user_display or None,
            title=display_title or content_to_store[:80],
            content=content_to_store,
            raw_content=(
                raw if matches and bool(getattr(settings, "kb_store_raw_content", False)) else None
            ),
            review_decision=decision,
            idempotency_key=idem_key,
        )
        indexing_debug: dict[str, Any] | None = None
        if self.indexing_pipeline is not None:
            try:
                indexing_debug = await self.indexing_pipeline.index_training_content(
                    kb_id=kb.id,
                    kb_uuid=kb.uuid,
                    collection=kb.qdrant_collection_name,
                    source_point_id=point_id,
                    sanitized_text=content_to_store,
                    title=display_title or content_to_store[:80],
                    current_user_id=current_user_id,
                )
            except Exception as e:
                # DB truth store megmarad; Qdrant drift esetén retry worker felveszi.
                self._enqueue_vector_outbox(
                    kb_id=kb.id,
                    operation_type="reindex_training_point",
                    payload={"kb_uuid": kb.uuid, "point_id": point_id},
                    source_point_id=point_id,
                )
                indexing_debug = {"queued_for_retry": True, "error": str(e)[:200]}
        pii_replaced_with_dots = False
        return {
            "status": "ok",
            "idempotent_replay": False,
            "point_id": point_id,
            "masked": masked,
            "pii_replaced_with_dots": pii_replaced_with_dots,
            "indexing": indexing_debug,
        }

    def list_training_log(
        self,
        kb_uuid: str,
        limit: int = 50,
        offset: int = 0,
        include_raw_content: bool = False,
    ) -> List[dict]:
        """Tanítási napló listája (train jog kell)."""
        return self.repo.list_training_log_paginated(
            kb_uuid=kb_uuid,
            limit=limit,
            offset=offset,
            include_raw_content=include_raw_content,
        )

    def list_personal_data_for_point(self, kb_uuid: str, point_id: str) -> List[dict]:
        """PII rekordok listázása adott train pointhoz (decrypted formában)."""
        kb = self.repo.get_by_uuid(kb_uuid)
        if not kb or kb.id is None:
            raise ValueError("KB not found")
        rows = self.repo.list_personal_data_by_point_id(kb.id, point_id)
        return [{"reference_id": ref_id, "value": value} for ref_id, value in rows]

    def get_training_point_source(self, kb_uuid: str, point_id: str) -> dict:
        """Forrásbejegyzés lekérése point_id alapján (sanitized content)."""
        kb = self.repo.get_by_uuid(kb_uuid)
        if not kb or kb.id is None:
            raise ValueError("KB not found")
        row = self.repo.get_training_log_entry(kb.id, point_id)
        if not row:
            raise ValueError("Training log entry not found")
        return {
            "kb_uuid": kb_uuid,
            "point_id": row.get("point_id"),
            "title": row.get("title") or "",
            "content": row.get("content") or "",
            "created_at": row.get("created_at"),
        }

    def purge_expired_personal_data(self) -> int:
        """Lejárt PII rekordok törlése."""
        return self.repo.purge_expired_personal_data()

    def dsar_search(self, kb_uuid: str, query: str, limit: int = 100, scan_limit: int = 2000) -> dict:
        kb = self.repo.get_by_uuid(kb_uuid)
        if not kb or kb.id is None:
            raise ValueError("KB not found")
        needle = _norm(query)
        if not needle:
            return {"items": [], "query_hash": _qhash(query), "matched": 0, "scanned": 0}
        records = self.repo.list_personal_data_records(kb.id, limit=scan_limit, offset=0)
        items: List[dict] = []
        for row in records:
            value = _norm(str(row.get("value", "")))
            if needle in value:
                items.append(
                    {
                        "reference_id": row.get("reference_id"),
                        "point_id": row.get("point_id"),
                        "data_type": row.get("data_type"),
                        "value": row.get("value"),
                        "created_at": row.get("created_at"),
                        "expires_at": row.get("expires_at"),
                    }
                )
                if len(items) >= limit:
                    break
        return {
            "items": items,
            "query_hash": _qhash(query),
            "matched": len(items),
            "scanned": len(records),
        }

    def dsar_delete(self, kb_uuid: str, query: str, limit: int = 100, scan_limit: int = 5000, dry_run: bool = False) -> dict:
        search = self.dsar_search(kb_uuid=kb_uuid, query=query, limit=limit, scan_limit=scan_limit)
        ref_ids = [x.get("reference_id") for x in search["items"] if x.get("reference_id")]
        if dry_run:
            return {
                "query_hash": search["query_hash"],
                "matched": search["matched"],
                "scanned": search["scanned"],
                "deleted": 0,
                "dry_run": True,
            }
        kb = self.repo.get_by_uuid(kb_uuid)
        if not kb or kb.id is None:
            raise ValueError("KB not found")
        deleted = self.repo.delete_personal_data_by_reference_ids(kb.id, ref_ids)
        return {
            "query_hash": search["query_hash"],
            "matched": search["matched"],
            "scanned": search["scanned"],
            "deleted": deleted,
            "dry_run": False,
        }

    def personal_data_metrics(self, kb_uuid: str) -> dict:
        kb = self.repo.get_by_uuid(kb_uuid)
        if not kb or kb.id is None:
            raise ValueError("KB not found")
        return self.repo.personal_data_metrics(kb.id)

    async def delete_training_point(self, kb_uuid: str, point_id: str) -> None:
        """Egy tanítási bejegyzés teljes törlése (derived + Qdrant + log)."""
        kb = self.repo.get_by_uuid(kb_uuid)
        if not kb or kb.id is None:
            raise ValueError("KB not found")
        self.repo.delete_derived_records_by_source_point_id(kb.id, point_id)
        try:
            await self.qdrant.delete_points_by_source_point_id(kb.qdrant_collection_name, point_id)
        except Exception:
            self._enqueue_vector_outbox(
                kb_id=kb.id,
                operation_type="delete_source_point",
                payload={"collection_name": kb.qdrant_collection_name, "source_point_id": point_id},
                source_point_id=point_id,
            )
        deleted = self.repo.delete_training_log_by_point_id(kb.id, point_id)
        if not deleted:
            raise ValueError("Training log entry not found")

    async def process_vector_outbox(self, limit: int = 50) -> dict:
        """Vector outbox elemek feldolgozása (retry worker/manual run)."""
        jobs = self.repo.list_due_vector_outbox(limit=limit)
        done = 0
        failed = 0
        failed_items: list[dict[str, Any]] = []
        for job in jobs:
            outbox_id = int(job.get("id"))
            op = str(job.get("operation_type") or "")
            payload = dict(job.get("payload") or {})
            attempts = int(job.get("attempts") or 0)
            try:
                if op == "delete_source_point":
                    await self.qdrant.delete_points_by_source_point_id(
                        payload.get("collection_name") or "",
                        payload.get("source_point_id") or "",
                    )
                elif op == "reindex_training_point":
                    await self.reindex_training_point(
                        kb_uuid=payload.get("kb_uuid") or "",
                        point_id=payload.get("point_id") or "",
                        current_user_id=None,
                    )
                else:
                    raise ValueError(f"Unknown outbox operation: {op}")
                self.repo.mark_vector_outbox_done(outbox_id)
                done += 1
                logger.info(
                    "kb_vector_outbox_done",
                    extra={
                        "outbox_id": outbox_id,
                        "operation_type": op,
                        "attempts": attempts,
                        "source_point_id": job.get("source_point_id"),
                    },
                )
            except Exception as e:
                # Exponenciális backoff plafonnal.
                backoff = min(3600, 2 ** min(10, attempts + 1))
                err = str(e)
                self.repo.mark_vector_outbox_retry(outbox_id, err, backoff_seconds=backoff)
                failed += 1
                failed_items.append(
                    {
                        "outbox_id": outbox_id,
                        "operation_type": op,
                        "attempts_before": attempts,
                        "retry_in_seconds": backoff,
                        "error": err[:300],
                    }
                )
                logger.warning(
                    "kb_vector_outbox_retry",
                    extra={
                        "outbox_id": outbox_id,
                        "operation_type": op,
                        "attempts_before": attempts,
                        "retry_in_seconds": backoff,
                        "error": err[:300],
                    },
                )
        return {
            "processed": len(jobs),
            "done": done,
            "failed": failed,
            "failed_items": failed_items,
        }

    def get_vector_outbox_stats(
        self,
        kb_uuid: str | None = None,
        recent_limit: int = 20,
    ) -> dict:
        """Vector outbox monitor statisztika lekérdezése."""
        kb_id: int | None = None
        if kb_uuid:
            kb = self.repo.get_by_uuid(kb_uuid)
            if not kb or kb.id is None:
                raise ValueError("KB not found")
            kb_id = kb.id
        stats = self.repo.get_vector_outbox_stats(kb_id=kb_id, recent_limit=recent_limit)
        return {
            **stats,
            "kb_uuid": kb_uuid,
        }

    def search_assertions(
        self,
        current_user_id: int,
        current_user_role: str | None,
        predicates: list[str] | None = None,
        entity_ids: list[int] | None = None,
        limit: int = 50,
    ) -> list[dict]:
        """Assertion keresés a user által elérhető KB-kon."""
        if current_user_role == "owner":
            kb_ids = [x.id for x in self.repo.list_all() if x.id is not None]
        else:
            kb_ids = self.repo.get_allowed_kb_ids_for_user(current_user_id)
        return self.repo.search_candidate_assertions(
            kb_ids=kb_ids,
            predicates=predicates,
            entity_ids=entity_ids,
            limit=limit,
        )

    async def reindex_training_point(self, kb_uuid: str, point_id: str, current_user_id: int | None = None) -> dict:
        """Egy train point újraindexelése meglévő sanitized contentből."""
        kb = self.repo.get_by_uuid(kb_uuid)
        if not kb or kb.id is None:
            raise ValueError("KB not found")
        if self.indexing_pipeline is None:
            return {"status": "skipped", "reason": "indexing_pipeline_not_configured"}
        rows = self.repo.list_training_log_paginated(kb_uuid=kb_uuid, limit=200, offset=0, include_raw_content=False)
        target = next((r for r in rows if r.get("point_id") == point_id), None)
        if not target:
            raise ValueError("Training log entry not found")
        self.repo.delete_derived_records_by_source_point_id(kb.id, point_id)
        await self.qdrant.delete_points_by_source_point_id(kb.qdrant_collection_name, point_id)
        result = await self.indexing_pipeline.index_training_content(
            kb_id=kb.id,
            kb_uuid=kb.uuid,
            collection=kb.qdrant_collection_name,
            source_point_id=point_id,
            sanitized_text=target.get("content") or "",
            title=target.get("title") or "",
            current_user_id=current_user_id,
        )
        return {"status": "ok", "result": result}

    async def reindex_kb(self, kb_uuid: str, current_user_id: int | None = None) -> dict:
        """Teljes KB újraindexelése a training logból."""
        kb = self.repo.get_by_uuid(kb_uuid)
        if not kb or kb.id is None:
            raise ValueError("KB not found")
        if self.indexing_pipeline is None:
            return {"status": "skipped", "reason": "indexing_pipeline_not_configured"}
        logs = self.repo.list_training_log_paginated(kb_uuid=kb_uuid, limit=20000, offset=0, include_raw_content=False)
        reindexed = 0
        for row in logs:
            point_id = row.get("point_id")
            if not point_id:
                continue
            self.repo.delete_derived_records_by_source_point_id(kb.id, point_id)
            await self.qdrant.delete_points_by_source_point_id(kb.qdrant_collection_name, point_id)
            await self.indexing_pipeline.index_training_content(
                kb_id=kb.id,
                kb_uuid=kb.uuid,
                collection=kb.qdrant_collection_name,
                source_point_id=point_id,
                sanitized_text=row.get("content") or "",
                title=row.get("title") or "",
                current_user_id=current_user_id,
            )
            reindexed += 1
        return {"status": "ok", "reindexed": reindexed}

    def reinforce_assertion(
        self,
        kb_uuid: str,
        assertion_id: int,
        event_type: str = "CHAT_RETRIEVAL_HIT",
    ) -> dict:
        """Assertion strength megerősítése esemény alapján."""
        kb = self.repo.get_by_uuid(kb_uuid)
        if not kb or kb.id is None:
            raise ValueError("KB not found")
        row = self.repo.get_assertion_by_id(kb.id, assertion_id)
        if not row:
            raise ValueError("Assertion not found")
        normalized_event = normalize_event_type(event_type)
        alpha = alpha_for_event(normalized_event)
        decayed = compute_current_strength(
            strength=float(row.get("strength") or 0.05),
            baseline_strength=float(row.get("baseline_strength") or 0.05),
            decay_rate=float(row.get("decay_rate") or 0.015),
            last_reinforced_at=row.get("last_reinforced_at"),
        )
        boosted = reinforce_strength(
            old_strength=decayed,
            alpha=alpha,
            baseline_strength=float(row.get("baseline_strength") or 0.05),
        )
        self.repo.update_assertion_strength(
            kb_id=kb.id,
            assertion_id=assertion_id,
            strength=boosted,
            last_reinforced_at=_utcnow_naive(),
            reinforcement_increment=1,
        )
        self.repo.add_reinforcement_event(
            kb_id=kb.id,
            target_type="assertion",
            target_id=assertion_id,
            event_type=normalized_event,
            weight=alpha,
        )
        return {"status": "ok", "assertion_id": assertion_id, "strength": boosted, "event_type": normalized_event}

    def decay_strengths_for_kb(self, kb_uuid: str, batch_limit: int = 2000) -> dict:
        """KB assertion strength mezők időalapú decay frissítése."""
        kb = self.repo.get_by_uuid(kb_uuid)
        if not kb or kb.id is None:
            raise ValueError("KB not found")
        rows = self.repo.list_assertions_for_kb(kb.id, limit=batch_limit, offset=0)
        updated = 0
        for row in rows:
            new_strength = decay_strength(
                current_strength=float(row.get("strength") or 0.05),
                baseline_strength=float(row.get("baseline_strength") or 0.05),
                decay_rate=float(row.get("decay_rate") or 0.015),
                delta_days=compute_delta_days(row.get("last_reinforced_at")),
            )
            changed = self.repo.update_assertion_strength(
                kb_id=kb.id,
                assertion_id=int(row["id"]),
                strength=new_strength,
                last_reinforced_at=row.get("last_reinforced_at"),
                reinforcement_increment=0,
            )
            if changed:
                updated += 1
        return {"status": "ok", "updated": updated}

    def recompute_strengths_for_kb(self, kb_uuid: str, batch_limit: int = 2000) -> dict:
        """Assertion strength újraszámolás current (decayed) értékre."""
        return self.decay_strengths_for_kb(kb_uuid=kb_uuid, batch_limit=batch_limit)

    def recompute_strengths_for_assertion_set(self, kb_uuid: str, assertion_ids: list[int]) -> dict:
        """Kijelölt assertion halmaz strength újraszámolása."""
        kb = self.repo.get_by_uuid(kb_uuid)
        if not kb or kb.id is None:
            raise ValueError("KB not found")
        updated = 0
        for assertion_id in assertion_ids:
            row = self.repo.get_assertion_by_id(kb.id, int(assertion_id))
            if not row:
                continue
            new_strength = compute_current_strength(
                strength=float(row.get("strength") or 0.05),
                baseline_strength=float(row.get("baseline_strength") or 0.05),
                decay_rate=float(row.get("decay_rate") or 0.015),
                last_reinforced_at=row.get("last_reinforced_at"),
            )
            if self.repo.update_assertion_strength(
                kb_id=kb.id,
                assertion_id=int(assertion_id),
                strength=new_strength,
                last_reinforced_at=row.get("last_reinforced_at"),
                reinforcement_increment=0,
            ):
                updated += 1
        return {"status": "ok", "updated": updated, "requested": len(assertion_ids)}

    async def recompute_local_relations_for_source_point(self, kb_uuid: str, source_point_id: str) -> dict:
        """Lokális relation újraépítés egy source point környezetében."""
        return await self.reindex_training_point(kb_uuid=kb_uuid, point_id=source_point_id, current_user_id=None)

    def recompute_assertion_statuses_for_kb(self, kb_uuid: str, batch_limit: int = 5000) -> dict:
        """Assertion státuszok újrabecslése relation/evidence alapján."""
        kb = self.repo.get_by_uuid(kb_uuid)
        if not kb or kb.id is None:
            raise ValueError("KB not found")
        rows = self.repo.list_assertions_for_kb(kb.id, limit=batch_limit, offset=0)
        updated = 0
        for row in rows:
            aid = int(row["id"])
            rels = self.repo.list_assertion_relations([aid], limit=120)
            status = determine_assertion_status(
                confidence=float(row.get("confidence") or 0.0),
                evidence_count=int(row.get("evidence_count") or 0),
                relations=rels,
            )
            if self.repo.update_assertion_status(kb_id=kb.id, assertion_id=aid, status=status):
                updated += 1
        return {"status": "ok", "updated": updated}

    async def rebuild_qdrant_payloads_for_kb(self, kb_uuid: str) -> dict:
        """Qdrant payloadok újraépítése reindexeléssel."""
        return await self.reindex_kb(kb_uuid=kb_uuid, current_user_id=None)

    def get_assertion_debug(self, kb_uuid: str, assertion_id: int) -> dict:
        """Assertion teljes debug nézet."""
        kb = self.repo.get_by_uuid(kb_uuid)
        if not kb or kb.id is None:
            raise ValueError("KB not found")
        return _sanitize_debug_value(self.repo.get_assertion_debug(kb.id, assertion_id))

    def get_entity_debug(self, kb_uuid: str, entity_id: int) -> dict:
        """Entity debug nézet aliasokkal és kapcsolatokkal."""
        kb = self.repo.get_by_uuid(kb_uuid)
        if not kb or kb.id is None:
            raise ValueError("KB not found")
        return _sanitize_debug_value(self.repo.get_entity_debug(kb.id, entity_id))

    def get_source_point_debug(self, kb_uuid: str, point_id: str) -> dict:
        """Source point debug nézet (assertion/sentence/chunk)."""
        kb = self.repo.get_by_uuid(kb_uuid)
        if not kb or kb.id is None:
            raise ValueError("KB not found")
        return _sanitize_debug_value(self.repo.get_source_point_debug(kb.id, point_id))

    def get_relation_bundle(self, kb_uuid: str, assertion_id: int) -> dict:
        """Assertion relation bundle lekérés."""
        kb = self.repo.get_by_uuid(kb_uuid)
        if not kb or kb.id is None:
            raise ValueError("KB not found")
        return self.repo.get_relation_bundle(kb.id, assertion_id, limit=120)

    def metric_snapshot(self, kb_uuid: str) -> dict:
        """KB állapot snapshot metrikák."""
        kb = self.repo.get_by_uuid(kb_uuid)
        if not kb or kb.id is None:
            raise ValueError("KB not found")
        return self.repo.get_metric_snapshot(kb.id)

    def confirm_assertion_relevance(self, kb_uuid: str, assertion_id: int) -> dict:
        """Felhasználói megerősítés hook assertionre."""
        return self.reinforce_assertion(kb_uuid=kb_uuid, assertion_id=assertion_id, event_type="USER_CONFIRMATION")

    def disconfirm_assertion_relevance(self, kb_uuid: str, assertion_id: int) -> dict:
        """Felhasználói ellenjelzés hook assertionre (óvatos gyengítés)."""
        kb = self.repo.get_by_uuid(kb_uuid)
        if not kb or kb.id is None:
            raise ValueError("KB not found")
        row = self.repo.get_assertion_by_id(kb.id, assertion_id)
        if not row:
            raise ValueError("Assertion not found")
        current = compute_current_strength(
            strength=float(row.get("strength") or 0.05),
            baseline_strength=float(row.get("baseline_strength") or 0.05),
            decay_rate=float(row.get("decay_rate") or 0.015),
            last_reinforced_at=row.get("last_reinforced_at"),
        )
        new_strength = max(float(row.get("baseline_strength") or 0.05), current * 0.85)
        self.repo.update_assertion_strength(
            kb_id=kb.id,
            assertion_id=assertion_id,
            strength=new_strength,
            last_reinforced_at=row.get("last_reinforced_at"),
            reinforcement_increment=0,
        )
        self.repo.add_reinforcement_event(
            kb_id=kb.id,
            target_type="assertion",
            target_id=assertion_id,
            event_type="INDIRECT_ACTIVATION",
            weight=-0.05,
        )
        return {"status": "ok", "assertion_id": assertion_id, "strength": new_strength}

    def merge_entities(self, kb_uuid: str, source_entity_id: int, target_entity_id: int) -> dict:
        """Két entitás összevonása (belső helper capability)."""
        kb = self.repo.get_by_uuid(kb_uuid)
        if not kb or kb.id is None:
            raise ValueError("KB not found")
        changed = self.repo.merge_entities(
            kb_id=kb.id,
            source_entity_id=source_entity_id,
            target_entity_id=target_entity_id,
        )
        return {
            "status": "ok" if changed else "noop",
            "kb_uuid": kb_uuid,
            "source_entity_id": source_entity_id,
            "target_entity_id": target_entity_id,
        }

    def build_context(self, current_user_id: int, current_user_role: str | None, limit: int = 25) -> dict:
        """Debug célú minimál context payload build."""
        assertions = self.search_assertions(
            current_user_id=current_user_id,
            current_user_role=current_user_role,
            predicates=None,
            entity_ids=None,
            limit=limit,
        )
        return {
            "top_assertions": assertions,
            "evidence_sentences": [],
            "source_chunks": [],
            "related_entities": [],
            "scoring_summary": {"items": len(assertions)},
        }

    def _resolve_kb_scope_for_user(
        self,
        current_user_id: int,
        current_user_role: str | None,
        kb_uuid: str | None = None,
    ) -> list[KnowledgeBase]:
        """Chat scope KB-k feloldása jogosultság alapján."""
        if kb_uuid:
            kb = self.repo.get_by_uuid(kb_uuid)
            if not kb or kb.id is None:
                raise ValueError("KB not found")
            if not self.user_can_use(kb_uuid, current_user_id, current_user_role):
                raise PermissionError("Nincs jogosultság a megadott tudástár használatához.")
            return [kb]

        if current_user_role == "owner":
            return [kb for kb in self.repo.list_all() if kb.id is not None]

        allowed = set(self.repo.get_allowed_kb_ids_for_user(current_user_id))
        return [kb for kb in self.repo.list_all() if kb.id is not None and kb.id in allowed]

    async def _resolve_query_entities(
        self,
        scoped_kbs: list[KnowledgeBase],
        parsed_query: dict,
        question: str,
    ) -> dict[str, list[dict]]:
        """Query entity jelöltek feloldása DB alias + canonical + Qdrant entity találatokból."""
        entity_terms = [str(x).strip() for x in parsed_query.get("entity_candidates", []) if str(x).strip()]
        if not entity_terms:
            return {}
        out: dict[str, list[dict]] = {}
        for kb in scoped_kbs:
            if kb.id is None:
                continue
            candidates: dict[int, dict] = {}
            for term in entity_terms:
                for row in self.repo.search_entity_candidates([kb.id], term, limit=12):
                    eid = int(row["id"])
                    existing = candidates.get(eid)
                    base = float(row.get("confidence") or 0.0)
                    score = min(1.0, 0.5 + base * 0.4)
                    if existing is None or score > float(existing.get("resolution_score") or 0.0):
                        candidates[eid] = {**row, "resolution_score": score, "resolution_source": "db"}

                try:
                    q_hits = await self.qdrant.search_points(
                        collection=kb.qdrant_collection_name,
                        query=term,
                        limit=8,
                        point_types=["entity"],
                        payload_filter={"kb_uuid": kb.uuid},
                    )
                except Exception:
                    q_hits = []
                for hit in q_hits:
                    payload = dict(hit.get("payload") or {})
                    raw_eid = payload.get("entity_id")
                    if raw_eid is None:
                        continue
                    try:
                        eid = int(raw_eid)
                    except Exception:
                        continue
                    score = min(1.0, float(hit.get("score") or 0.0))
                    existing = candidates.get(eid)
                    row = {
                        "id": eid,
                        "kb_id": kb.id,
                        "canonical_name": payload.get("canonical_name"),
                        "entity_type": payload.get("entity_type"),
                        "aliases": payload.get("aliases") or [],
                        "confidence": float(payload.get("confidence") or 0.0),
                        "resolution_score": score,
                        "resolution_source": "qdrant",
                    }
                    if existing is None or score > float(existing.get("resolution_score") or 0.0):
                        candidates[eid] = row
            out[kb.uuid] = sorted(candidates.values(), key=lambda x: float(x.get("resolution_score") or 0.0), reverse=True)[:10]
        parsed_query["resolved_entity_candidates"] = {
            kb_uuid: [
                {
                    "entity_id": int(x["id"]),
                    "canonical_name": x.get("canonical_name"),
                    "entity_type": x.get("entity_type"),
                    "resolution_score": float(x.get("resolution_score") or 0.0),
                }
                for x in rows
            ]
            for kb_uuid, rows in out.items()
        }
        parsed_query["resolved_entity_ids"] = {
            kb_uuid: [int(x["id"]) for x in rows]
            for kb_uuid, rows in out.items()
        }
        parsed_query["entity_resolution_query"] = question
        return out

    @staticmethod
    def _compute_place_match(
        query_terms: list[str],
        resolved_keys: set[str],
        hierarchy_keys: set[str],
        item_place_keys: list[str],
        item_place_hierarchy_keys: list[str] | None = None,
    ) -> float:
        if not query_terms and not resolved_keys and not hierarchy_keys:
            return 0.0
        item_keys = {_normalize_place_key(x) for x in item_place_keys if _normalize_place_key(x)}
        item_hierarchy_keys = {
            _normalize_place_key(x)
            for x in (item_place_hierarchy_keys or [])
            if _normalize_place_key(x)
        }
        all_item_keys = item_keys.union(item_hierarchy_keys)
        if not all_item_keys:
            return 0.0
        if resolved_keys and all_item_keys.intersection(resolved_keys):
            return 1.0
        if hierarchy_keys and all_item_keys.intersection(hierarchy_keys):
            return 0.84 if item_hierarchy_keys else 0.72
        for q in query_terms:
            qn = _normalize_place_key(q)
            if not qn:
                continue
            if any(qn in ik or ik in qn for ik in all_item_keys):
                return 0.5
        return 0.0

    @staticmethod
    def _build_related_places(packet: dict[str, Any], query_place_keys: list[str]) -> list[dict[str, Any]]:
        place_map: dict[str, dict[str, Any]] = {}
        for bucket_name in ("top_assertions", "expanded_assertions", "evidence_sentences", "source_chunks"):
            for row in (packet.get(bucket_name) or []):
                if not isinstance(row, dict):
                    continue
                for place_key in _row_place_keys(row):
                    item = place_map.setdefault(
                        place_key,
                        {
                            "place_key": place_key,
                            "kb_uuids": [],
                            "assertion_ids": [],
                            "seed_assertion_ids": [],
                            "expanded_assertion_ids": [],
                            "evidence_sentence_ids": [],
                            "source_point_ids": [],
                            "query_match": 0.0,
                        },
                    )
                    kb_uuid = str(row.get("kb_uuid") or "").strip()
                    if kb_uuid and kb_uuid not in item["kb_uuids"]:
                        item["kb_uuids"].append(kb_uuid)
                    source_point_id = str(row.get("source_point_id") or "").strip()
                    if source_point_id and source_point_id not in item["source_point_ids"]:
                        item["source_point_ids"].append(source_point_id)
                    place_match = float(row.get("place_match") or 0.0)
                    if query_place_keys and place_key in query_place_keys:
                        place_match = max(place_match, 1.0)
                    item["query_match"] = max(float(item.get("query_match") or 0.0), place_match)
                    if bucket_name in {"top_assertions", "expanded_assertions"}:
                        assertion_id = _parse_assertion_id(row.get("id"))
                        if assertion_id is not None and assertion_id not in item["assertion_ids"]:
                            item["assertion_ids"].append(assertion_id)
                        if bucket_name == "top_assertions" and assertion_id is not None and assertion_id not in item["seed_assertion_ids"]:
                            item["seed_assertion_ids"].append(assertion_id)
                        if bucket_name == "expanded_assertions" and assertion_id is not None and assertion_id not in item["expanded_assertion_ids"]:
                            item["expanded_assertion_ids"].append(assertion_id)
                    elif bucket_name == "evidence_sentences":
                        sentence_id = row.get("sentence_id")
                        if sentence_id is not None and sentence_id not in item["evidence_sentence_ids"]:
                            item["evidence_sentence_ids"].append(sentence_id)
        places = list(place_map.values())
        places.sort(
            key=lambda x: (
                -len(x.get("seed_assertion_ids") or []),
                -float(x.get("query_match") or 0.0),
                -len(x.get("assertion_ids") or []),
                x.get("place_key") or "",
            )
        )
        return places[:12]

    async def _resolve_query_places(
        self,
        scoped_kbs: list[KnowledgeBase],
        parsed_query: dict,
    ) -> dict[str, list[str]]:
        """Hely jelöltek feloldása Qdrant payload place kulcsok alapján."""
        place_terms = _dedupe_keep_order(
            [
                _normalize_place_key(str(x))
                for x in (parsed_query.get("place_candidates") or [])
                if _normalize_place_key(str(x))
            ]
        )
        parser_resolved_raw = parsed_query.get("resolved_place_candidates") or []
        parser_resolved: list[Any]
        if isinstance(parser_resolved_raw, dict):
            parser_resolved = []
            for values in parser_resolved_raw.values():
                if isinstance(values, list):
                    parser_resolved.extend(values)
        elif isinstance(parser_resolved_raw, list):
            parser_resolved = parser_resolved_raw
        else:
            parser_resolved = [parser_resolved_raw]
        parser_place_terms = [
            _normalize_place_key(x.get("normalized_key") if isinstance(x, dict) else x)
            for x in parser_resolved
        ]
        if not place_terms:
            parsed_query["resolved_place_candidates"] = {}
            parsed_query["resolved_place_hierarchy_keys"] = {}
            return {}
        out: dict[str, list[str]] = {}
        hierarchy_out: dict[str, list[str]] = {}
        for kb in scoped_kbs:
            resolved: set[str] = set()
            hierarchy_keys: set[str] = set()
            db_place_ids: set[int] = set()
            terms = sorted(set(place_terms + [x for x in parser_place_terms if x]))
            for term in terms:
                if kb.id is not None and hasattr(self.repo, "search_place_candidates"):
                    for row in self.repo.search_place_candidates(kb.id, term, limit=12):
                        p_key = _normalize_place_key(row.get("normalized_key") or row.get("canonical_name") or "")
                        if p_key:
                            resolved.add(p_key)
                        try:
                            db_place_ids.add(int(row.get("id")))
                        except Exception:
                            pass
                try:
                    hits = await self.qdrant.search_points(
                        collection=kb.qdrant_collection_name,
                        query=term,
                        limit=10,
                        point_types=["assertion", "sentence", "structural_chunk"],
                        payload_filter={"kb_uuid": kb.uuid},
                    )
                except Exception:
                    hits = []
                for hit in hits:
                    payload = dict(hit.get("payload") or {})
                    for p in payload.get("place_keys") or []:
                        place_key = str(p or "").strip().lower()
                        if not place_key:
                            continue
                        if term == place_key or term in place_key or place_key in term:
                            resolved.add(place_key)
                    place_key = str(payload.get("place_key") or "").strip().lower()
                    if place_key and (term == place_key or term in place_key or place_key in term):
                        resolved.add(place_key)
            if kb.id is not None and db_place_ids and hasattr(self.repo, "get_place_hierarchy"):
                hierarchy_map = self.repo.get_place_hierarchy(kb.id, list(db_place_ids), max_depth=4)
                for chain in hierarchy_map.values():
                    for row in chain:
                        h_key = _normalize_place_key(row.get("normalized_key") or row.get("canonical_name") or "")
                        if h_key:
                            hierarchy_keys.add(h_key)
            out[kb.uuid] = sorted(resolved)
            hierarchy_out[kb.uuid] = sorted(hierarchy_keys)
        parsed_query["resolved_place_candidates"] = out
        parsed_query["resolved_place_hierarchy_keys"] = hierarchy_out
        return out

    async def build_context_for_chat(
        self,
        question: str,
        current_user_id: int,
        current_user_role: str | None,
        parsed_query: dict,
        kb_uuid: str | None = None,
        per_type_limit: int = 8,
    ) -> dict:
        """Query parse + retrieval + rerank + context assembly."""
        scoped_kbs = self._resolve_kb_scope_for_user(
            current_user_id=current_user_id,
            current_user_role=current_user_role,
            kb_uuid=kb_uuid,
        )
        if not scoped_kbs:
            return {
                "top_assertions": [],
                "evidence_sentences": [],
                "source_chunks": [],
                "related_entities": [],
                "scoring_summary": {"kb_count": 0, "query": question},
            }

        parsed_query = dict(parsed_query or {})
        query_representation = _compose_query_representation(question=question, parsed_query=parsed_query)
        parsed_query.setdefault("raw_query", question)
        normalized_query_text_value = str(
            parsed_query.get("normalized_query_text")
            or parsed_query.get("lexical_query_text")
            or parsed_query.get("query_embedding_text")
            or query_representation["normalized_query_text"]
        )
        lexical_query_text_value = str(
            parsed_query.get("lexical_query_text")
            or parsed_query.get("normalized_query_text")
            or parsed_query.get("query_embedding_text")
            or query_representation["lexical_query_text"]
        )
        query_embedding_text_value = str(
            parsed_query.get("query_embedding_text")
            or parsed_query.get("normalized_query_text")
            or parsed_query.get("lexical_query_text")
            or query_representation["query_embedding_text"]
        )
        parsed_query["normalized_query_text"] = normalized_query_text_value
        parsed_query["lexical_query_text"] = lexical_query_text_value
        parsed_query["query_embedding_text"] = query_embedding_text_value
        parsed_query.setdefault("parser_audit", {})
        parsed_query["parser_audit"]["knowledge_query_representation"] = {
            "normalized_query_text": parsed_query.get("normalized_query_text"),
            "lexical_query_text": parsed_query.get("lexical_query_text"),
            "query_embedding_text": parsed_query.get("query_embedding_text"),
            "entity_candidates": parsed_query.get("entity_candidates") or [],
            "time_candidates": parsed_query.get("time_candidates") or [],
            "place_candidates": parsed_query.get("place_candidates") or [],
            "predicate_candidates": parsed_query.get("predicate_candidates") or [],
            "attribute_candidates": parsed_query.get("attribute_candidates") or [],
            "relation_candidates": parsed_query.get("relation_candidates") or [],
            "intent": parsed_query.get("intent"),
            "retrieval_mode": parsed_query.get("retrieval_mode"),
        }

        entity_terms = [str(x).strip().lower() for x in parsed_query.get("entity_candidates", []) if str(x).strip()]
        query_valid_time_from = parsed_query.get("query_valid_time_from") or parsed_query.get("query_time_from")
        query_valid_time_to = parsed_query.get("query_valid_time_to") or parsed_query.get("query_time_to")
        query_valid_time_window = {
            "from": _iso_or_none(query_valid_time_from),
            "to": _iso_or_none(query_valid_time_to),
        }
        place_terms = _dedupe_keep_order(
            [
                _normalize_place_key(str(x))
                for x in (parsed_query.get("place_candidates") or [])
                if _normalize_place_key(str(x))
            ]
        )
        predicate_terms = [str(x).strip().lower() for x in parsed_query.get("predicate_candidates", []) if str(x).strip()]
        attribute_terms = [str(x).strip().lower() for x in parsed_query.get("attribute_candidates", []) if str(x).strip()]
        relation_terms = [str(x).strip().lower() for x in parsed_query.get("relation_candidates", []) if str(x).strip()]
        lexical_focus_terms = [
            str(x).strip().lower()
            for x in (parsed_query.get("lexical_focus_terms") or [])
            if str(x).strip()
        ]
        exact_phrase_candidates = [
            str(x).strip().lower()
            for x in (parsed_query.get("exact_phrase_candidates") or [])
            if str(x).strip()
        ]
        hybrid_profile = dict(parsed_query.get("hybrid_profile") or {})
        rare_entity_terms = [
            str(x).strip().lower()
            for x in (hybrid_profile.get("rare_entity_terms") or parsed_query.get("rare_entity_terms") or [])
            if str(x).strip()
        ]
        retrieval_mode = str(parsed_query.get("retrieval_mode") or "assertion_first")
        if bool(parsed_query.get("entity_heavy")) and retrieval_mode == "assertion_first":
            retrieval_mode = "entity_first"
        query_text = str(parsed_query.get("query_embedding_text") or question)
        normalized_query_text = str(parsed_query.get("normalized_query_text") or query_text or question)
        lexical_query_text = str(parsed_query.get("lexical_query_text") or normalized_query_text or query_text)
        request_query_vector = parsed_query.get("query_embedding_vector")
        if isinstance(request_query_vector, (list, tuple)) and len(request_query_vector) == 0:
            request_query_vector = None
        parsed_query["query_embedding_prepare_calls"] = int(parsed_query.get("query_embedding_prepare_calls") or 0) + 1
        if request_query_vector is None and hasattr(self.qdrant, "embed_text"):
            t_embed = perf_counter()
            try:
                request_query_vector = await self.qdrant.embed_text(query_text)
                parsed_query["query_embedding_vector"] = list(request_query_vector or [])
                parsed_query["query_embedding_generation_count"] = int(parsed_query.get("query_embedding_generation_count") or 0) + 1
                parsed_query["query_embedding_time_ms"] = round(
                    float(parsed_query.get("query_embedding_time_ms") or 0.0) + ((perf_counter() - t_embed) * 1000.0),
                    2,
                )
            except Exception:
                request_query_vector = None
        t_total_start = perf_counter()
        qdrant_latency_ms = 0.0
        db_latency_ms = 0.0
        context_build_ms = 0.0
        qdrant_search_calls = 0
        qdrant_precomputed_vector_calls = 0

        assertion_hits: list[dict] = []
        sentence_hits: list[dict] = []
        chunk_hits: list[dict] = []
        related_entities: list[dict] = []
        qdrant_search_cache: dict[str, list[dict[str, Any]]] = {}
        resolved_entities_by_kb = await self._resolve_query_entities(scoped_kbs, parsed_query, question)
        resolved_places_by_kb = await self._resolve_query_places(scoped_kbs, parsed_query)
        resolved_place_hierarchy_by_kb = parsed_query.get("resolved_place_hierarchy_keys") or {}

        def _hybrid_weights_for(point_type: str) -> tuple[float, float]:
            is_entity_heavy = bool(parsed_query.get("entity_heavy"))
            is_predicate_heavy = bool(parsed_query.get("predicate_heavy"))
            is_relation_heavy = bool(hybrid_profile.get("relation_heavy"))
            has_rare_entities = bool(rare_entity_terms)
            has_exact_phrases = bool(exact_phrase_candidates)
            if point_type == "assertion":
                semantic_w, lexical_w = 0.72, 0.28
                if has_exact_phrases or is_entity_heavy or has_rare_entities:
                    semantic_w, lexical_w = 0.50, 0.50
                elif is_predicate_heavy or is_relation_heavy:
                    semantic_w, lexical_w = 0.58, 0.42
            elif point_type == "sentence":
                semantic_w, lexical_w = 0.62, 0.38
                if retrieval_mode == "chunk_fallback":
                    semantic_w, lexical_w = 0.46, 0.54
                elif has_exact_phrases or is_entity_heavy or has_rare_entities:
                    semantic_w, lexical_w = 0.48, 0.52
            else:
                semantic_w, lexical_w = 0.64, 0.36
                if retrieval_mode == "chunk_fallback":
                    semantic_w, lexical_w = 0.42, 0.58
                elif is_predicate_heavy or is_relation_heavy:
                    semantic_w, lexical_w = 0.58, 0.42
            return semantic_w, lexical_w

        def _merge_hybrid_hits(
            dense_hits: list[dict[str, Any]],
            lexical_hits: list[dict[str, Any]],
            *,
            limit_for_type: int,
            semantic_weight: float,
            lexical_weight: float,
        ) -> list[dict[str, Any]]:
            merged_by_id: dict[str, dict[str, Any]] = {}
            for source_name, hits in (("dense", dense_hits), ("lexical", lexical_hits)):
                for hit in hits:
                    hid = str(hit.get("id"))
                    if not hid:
                        continue
                    row = merged_by_id.setdefault(
                        hid,
                        {
                            "row": dict(hit),
                            "semantic_raw": [],
                            "lexical_raw": [],
                            "sources": set(),
                            "exact_phrase_score": 0.0,
                            "rare_score": 0.0,
                            "focus_term_score": 0.0,
                        },
                    )
                    row["semantic_raw"].append(float(hit.get("semantic_score") or hit.get("semantic_score_norm") or hit.get("score") or 0.0))
                    row["lexical_raw"].append(float(hit.get("lexical_score") or hit.get("lexical_score_norm") or 0.0))
                    row["sources"].add(source_name)
                    lexical_features = dict(hit.get("lexical_features") or {})
                    row["exact_phrase_score"] = max(row["exact_phrase_score"], float(lexical_features.get("exact_phrase_score") or 0.0))
                    row["rare_score"] = max(row["rare_score"], float(lexical_features.get("rare_score") or 0.0))
                    row["focus_term_score"] = max(row["focus_term_score"], float(lexical_features.get("focus_term_score") or 0.0))
                    if float(hit.get("fusion_score") or 0.0) >= float(row["row"].get("fusion_score") or 0.0):
                        row["row"] = dict(hit)
            if not merged_by_id:
                return []
            semantic_values = [max(entry["semantic_raw"]) if entry["semantic_raw"] else 0.0 for entry in merged_by_id.values()]
            lexical_values = [max(entry["lexical_raw"]) if entry["lexical_raw"] else 0.0 for entry in merged_by_id.values()]
            sem_min, sem_max = min(semantic_values), max(semantic_values)
            lex_min, lex_max = min(lexical_values), max(lexical_values)
            out: list[dict[str, Any]] = []
            for entry in merged_by_id.values():
                row = dict(entry["row"])
                sem_best = max(entry["semantic_raw"]) if entry["semantic_raw"] else 0.0
                lex_best = max(entry["lexical_raw"]) if entry["lexical_raw"] else 0.0
                sem_norm = _normalize_score_range(sem_best, sem_min, sem_max)
                lex_norm = _normalize_score_range(lex_best, lex_min, lex_max)
                coverage_bonus = 0.06 if len(entry["sources"]) > 1 else 0.0
                lexical_bonus = (
                    (0.08 * float(entry["exact_phrase_score"]))
                    + (0.06 * float(entry["rare_score"]))
                    + (0.04 * float(entry["focus_term_score"]))
                )
                row["semantic_score_norm"] = sem_norm
                row["lexical_score_norm"] = lex_norm
                row["fusion_score"] = _clamp01((semantic_weight * sem_norm) + (lexical_weight * lex_norm) + coverage_bonus + lexical_bonus)
                row["fusion_debug"] = {
                    "source_count": len(entry["sources"]),
                    "sources": sorted(entry["sources"]),
                    "coverage_bonus": round(coverage_bonus, 4),
                    "exact_phrase_score": round(float(entry["exact_phrase_score"]), 4),
                    "rare_score": round(float(entry["rare_score"]), 4),
                    "focus_term_score": round(float(entry["focus_term_score"]), 4),
                }
                out.append(row)
            out.sort(key=lambda x: float(x.get("fusion_score") or x.get("score") or 0.0), reverse=True)
            return out[:limit_for_type]

        async def _cached_search(
            kb: KnowledgeBase,
            query_value: str,
            lexical_query_value: str,
            point_type: str,
            limit_value: int,
            payload_filter_value: dict[str, Any],
            fusion_semantic_weight_value: float,
            fusion_lexical_weight_value: float,
            lexical_focus_terms_value: list[str],
            exact_phrases_value: list[str],
            rare_terms_value: list[str],
        ) -> list[dict[str, Any]]:
            cache_key = json.dumps(
                {
                    "collection": kb.qdrant_collection_name,
                    "query": query_value,
                    "lexical_query": lexical_query_value,
                    "point_type": point_type,
                    "limit": limit_value,
                    "filter": payload_filter_value,
                    "fusion_semantic_weight": fusion_semantic_weight_value,
                    "fusion_lexical_weight": fusion_lexical_weight_value,
                    "lexical_focus_terms": lexical_focus_terms_value,
                    "exact_phrases": exact_phrases_value,
                    "rare_terms": rare_terms_value,
                },
                sort_keys=True,
                default=str,
            )
            if cache_key in qdrant_search_cache:
                return qdrant_search_cache[cache_key]
            t_q = perf_counter()
            try:
                rows = await self.qdrant.search_points(
                    collection=kb.qdrant_collection_name,
                    query=query_value,
                    limit=limit_value,
                    point_types=[point_type],
                    payload_filter=payload_filter_value,
                    query_vector=request_query_vector,
                    lexical_query=lexical_query_value,
                    fusion_semantic_weight=fusion_semantic_weight_value,
                    fusion_lexical_weight=fusion_lexical_weight_value,
                    lexical_focus_terms=lexical_focus_terms_value,
                    exact_phrases=exact_phrases_value,
                    rare_terms=rare_terms_value,
                )
            except TypeError as exc:
                # Régi/mockolt qdrant adapterek csak az alap paramétereket ismerik.
                if "unexpected keyword argument" not in str(exc):
                    raise
                rows = await self.qdrant.search_points(
                    collection=kb.qdrant_collection_name,
                    query=query_value,
                    limit=limit_value,
                    point_types=[point_type],
                    payload_filter=payload_filter_value,
                )
            except StopAsyncIteration:
                rows = []
            nonlocal qdrant_latency_ms
            nonlocal qdrant_search_calls
            nonlocal qdrant_precomputed_vector_calls
            qdrant_latency_ms += (perf_counter() - t_q) * 1000.0
            qdrant_search_calls += 1
            if request_query_vector is not None:
                qdrant_precomputed_vector_calls += 1
            qdrant_search_cache[cache_key] = rows
            return rows

        for kb in scoped_kbs:
            place_filter = resolved_places_by_kb.get(kb.uuid) or place_terms or None
            kb_place_resolved_keys = set(resolved_places_by_kb.get(kb.uuid) or [])
            kb_place_hierarchy_keys = set(resolved_place_hierarchy_by_kb.get(kb.uuid) or [])
            kb_resolved_ids = [int(x["id"]) for x in (resolved_entities_by_kb.get(kb.uuid) or []) if x.get("id") is not None]
            assertion_limit = per_type_limit + (2 if bool(parsed_query.get("entity_heavy")) else 0)
            sentence_limit = max(3, per_type_limit // 2)
            chunk_limit = max(2, per_type_limit // 3)
            if retrieval_mode == "chunk_fallback":
                point_type_order = [
                    ("sentence", sentence_hits, sentence_limit),
                    ("structural_chunk", chunk_hits, chunk_limit),
                    ("assertion", assertion_hits, assertion_limit),
                ]
            elif retrieval_mode == "entity_first":
                point_type_order = [
                    ("assertion", assertion_hits, assertion_limit + 2),
                    ("sentence", sentence_hits, sentence_limit),
                    ("structural_chunk", chunk_hits, chunk_limit),
                ]
            elif retrieval_mode == "timeline_first":
                point_type_order = [
                    ("assertion", assertion_hits, assertion_limit + 3),
                    ("sentence", sentence_hits, sentence_limit + 1),
                    ("structural_chunk", chunk_hits, chunk_limit),
                ]
            elif retrieval_mode == "comparison_first":
                point_type_order = [
                    ("assertion", assertion_hits, assertion_limit + 4),
                    ("sentence", sentence_hits, sentence_limit + 1),
                    ("structural_chunk", chunk_hits, chunk_limit),
                ]
            else:
                point_type_order = [
                    ("assertion", assertion_hits, assertion_limit),
                    ("sentence", sentence_hits, sentence_limit),
                    ("structural_chunk", chunk_hits, chunk_limit),
                ]
            assertion_hits_before = len(assertion_hits)
            sentence_hits_before = len(sentence_hits)
            for point_type, target, limit_for_type in point_type_order:
                if point_type == "sentence" and retrieval_mode != "chunk_fallback":
                    if (len(assertion_hits) - assertion_hits_before) >= 3:
                        continue
                if point_type == "structural_chunk" and retrieval_mode != "chunk_fallback":
                    if ((len(assertion_hits) - assertion_hits_before) + (len(sentence_hits) - sentence_hits_before)) >= 4:
                        continue
                base_filter = {
                    "kb_uuid": kb.uuid,
                    "place_keys": place_filter,
                    "entity_ids": kb_resolved_ids if kb_resolved_ids else None,
                }
                f_sem, f_lex = _hybrid_weights_for(point_type)
                if point_type == "assertion":
                    hits_dense = await _cached_search(
                        kb=kb,
                        query_value=query_text,
                        lexical_query_value=lexical_query_text,
                        point_type=point_type,
                        limit_value=max(limit_for_type, 1),
                        payload_filter_value=base_filter,
                        fusion_semantic_weight_value=f_sem,
                        fusion_lexical_weight_value=f_lex,
                        lexical_focus_terms_value=lexical_focus_terms,
                        exact_phrases_value=exact_phrase_candidates,
                        rare_terms_value=rare_entity_terms,
                    )
                    hits_lexical = await _cached_search(
                        kb=kb,
                        query_value=lexical_query_text,
                        lexical_query_value=lexical_query_text,
                        point_type=point_type,
                        limit_value=max(2, limit_for_type // 2),
                        payload_filter_value=base_filter,
                        fusion_semantic_weight_value=f_sem,
                        fusion_lexical_weight_value=f_lex,
                        lexical_focus_terms_value=lexical_focus_terms,
                        exact_phrases_value=exact_phrase_candidates,
                        rare_terms_value=rare_entity_terms,
                    )
                    hits = _merge_hybrid_hits(
                        hits_dense,
                        hits_lexical,
                        limit_for_type=limit_for_type,
                        semantic_weight=f_sem,
                        lexical_weight=f_lex,
                    )
                else:
                    hits = await _cached_search(
                        kb=kb,
                        query_value=lexical_query_text or query_text,
                        lexical_query_value=lexical_query_text,
                        point_type=point_type,
                        limit_value=max(limit_for_type, 1),
                        payload_filter_value=base_filter,
                        fusion_semantic_weight_value=f_sem,
                        fusion_lexical_weight_value=f_lex,
                        lexical_focus_terms_value=lexical_focus_terms,
                        exact_phrases_value=exact_phrase_candidates,
                        rare_terms_value=rare_entity_terms,
                    )
                for hit in hits:
                    payload = dict(hit.get("payload") or {})
                    text = str(payload.get("text") or "").strip()
                    lowered = text.lower()
                    entity_match = 1.0 if entity_terms and any(t in lowered for t in entity_terms) else 0.0
                    time_match = compute_time_overlap_score(
                        query_from=query_valid_time_from,
                        query_to=query_valid_time_to,
                        item_from=payload.get("valid_time_from") or payload.get("time_from"),
                        item_to=payload.get("valid_time_to") or payload.get("time_to"),
                    )
                    payload_place_keys = [
                        _normalize_place_key(x)
                        for x in (payload.get("place_keys") or [])
                        if _normalize_place_key(x)
                    ]
                    single_place = _normalize_place_key(payload.get("place_key") or "")
                    if single_place:
                        payload_place_keys.append(single_place)
                    place_match = self._compute_place_match(
                        query_terms=place_terms,
                        resolved_keys=kb_place_resolved_keys,
                        hierarchy_keys=kb_place_hierarchy_keys,
                        item_place_keys=payload_place_keys,
                        item_place_hierarchy_keys=payload.get("place_hierarchy_keys") or [],
                    )
                    predicate_match = 1.0 if predicate_terms and any(t in lowered for t in predicate_terms) else 0.0
                    if attribute_terms and any(t in lowered for t in attribute_terms):
                        predicate_match = max(predicate_match, 0.8)
                    if relation_terms and any(t in lowered for t in relation_terms):
                        predicate_match = max(predicate_match, 0.7)
                    payload_entities = payload.get("entity_ids") or []
                    status = str(payload.get("status") or "active").lower()
                    related_entities.extend(
                        [{"entity_id": x, "kb_uuid": kb.uuid} for x in payload_entities if x is not None]
                    )
                    target.append(
                        {
                            "id": hit.get("id"),
                            "kb_uuid": kb.uuid,
                            "point_type": point_type,
                            "source_point_id": payload.get("source_point_id"),
                            "source_sentence_id": payload.get("source_sentence_id"),
                            "text": text,
                            "semantic_match": float(hit.get("semantic_score_norm") or hit.get("semantic_score") or hit.get("score") or 0.0),
                            "lexical_match": float(hit.get("lexical_score_norm") or hit.get("lexical_score") or 0.0),
                            "fusion_match": float(hit.get("fusion_score") or 0.0),
                            "hybrid_debug": hit.get("fusion_debug") or {},
                            "entity_match": entity_match,
                            "time_match": time_match,
                            "place_match": place_match,
                            "predicate_match": predicate_match,
                            "graph_proximity": 0.0,  # lokális kapcsolatokból később finomítható
                            "strength": float(payload.get("strength") or 0.0),
                            "baseline_strength": float(payload.get("baseline_strength") or 0.05),
                            "decay_rate": float(payload.get("decay_rate") or 0.015),
                            "last_reinforced_at": payload.get("last_reinforced_at"),
                            "confidence": float(payload.get("confidence") or 0.0),
                            "source_time": payload.get("source_time"),
                            "ingest_time": payload.get("ingest_time"),
                            "time_semantics": {
                                "valid_time": {
                                    "from": _iso_or_none(payload.get("valid_time_from") or payload.get("time_from")),
                                    "to": _iso_or_none(payload.get("valid_time_to") or payload.get("time_to")),
                                },
                                "source_time": _iso_or_none(payload.get("source_time")),
                                "ingest_time": _iso_or_none(payload.get("ingest_time")),
                            },
                            "status": status,
                            "predicate": payload.get("predicate"),
                            "entity_ids": payload_entities,
                            "place_ids": payload.get("place_ids") or [],
                            "place_keys": payload.get("place_keys") or ([payload.get("place_key")] if payload.get("place_key") else []),
                            "place_hierarchy_keys": payload.get("place_hierarchy_keys") or [],
                            "valid_time_from": payload.get("valid_time_from") or payload.get("time_from"),
                            "valid_time_to": payload.get("valid_time_to") or payload.get("time_to"),
                            "time_from": payload.get("valid_time_from") or payload.get("time_from"),
                            "time_to": payload.get("valid_time_to") or payload.get("time_to"),
                            "relation_weight": 0.0,
                            "relation_confidence": 0.0,
                            "relation_depth": None,
                            "is_seed": point_type == "assertion",
                        }
                    )

            if kb.id is not None and (kb_resolved_ids or predicate_terms):
                candidate_rows = self.repo.search_candidate_assertions(
                    kb_ids=[kb.id],
                    predicates=predicate_terms or None,
                    entity_ids=kb_resolved_ids or None,
                    limit=max(6, per_type_limit + 4),
                )
                candidate_place_hierarchy_map = self.repo.get_place_hierarchy(
                    kb.id,
                    [int(row.get("place_id")) for row in candidate_rows if row.get("place_id") is not None],
                    max_depth=4,
                ) if candidate_rows and hasattr(self.repo, "get_place_hierarchy") else {}
                existing_by_id = {str(row.get("id")): row for row in assertion_hits if str(row.get("kb_uuid") or "") == kb.uuid}
                for row in candidate_rows:
                    row_id = f"assertion-{int(row['id'])}"
                    place_hierarchy_keys = [
                        _normalize_place_key(x.get("normalized_key") or x.get("canonical_name") or "")
                        for x in (candidate_place_hierarchy_map.get(int(row.get("place_id"))) or [])
                        if _normalize_place_key(x.get("normalized_key") or x.get("canonical_name") or "")
                    ] if row.get("place_id") is not None else []
                    candidate_entity_ids = [
                        x for x in [row.get("subject_entity_id"), row.get("object_entity_id")]
                        if isinstance(x, int)
                    ]
                    entity_match = 1.0 if kb_resolved_ids and any(int(x) in kb_resolved_ids for x in candidate_entity_ids) else 0.0
                    predicate_match = 1.0 if predicate_terms and str(row.get("predicate") or "").strip().lower() in predicate_terms else 0.0
                    time_match = compute_time_overlap_score(
                        query_from=query_valid_time_from,
                        query_to=query_valid_time_to,
                        item_from=row.get("valid_time_from") or row.get("time_from"),
                        item_to=row.get("valid_time_to") or row.get("time_to"),
                    )
                    place_match = self._compute_place_match(
                        query_terms=place_terms,
                        resolved_keys=kb_place_resolved_keys,
                        hierarchy_keys=kb_place_hierarchy_keys,
                        item_place_keys=_row_place_keys(row),
                        item_place_hierarchy_keys=place_hierarchy_keys,
                    )
                    hint_score = _clamp01(
                        0.18
                        + (0.28 * entity_match)
                        + (0.20 * predicate_match)
                        + (0.16 * time_match)
                        + (0.14 * place_match)
                        + (0.02 * float(row.get("confidence") or 0.0))
                        + (0.02 * float(row.get("strength") or 0.0))
                    )
                    existing = existing_by_id.get(row_id)
                    if existing is not None:
                        existing["entity_match"] = max(float(existing.get("entity_match") or 0.0), entity_match)
                        existing["predicate_match"] = max(float(existing.get("predicate_match") or 0.0), predicate_match)
                        existing["time_match"] = max(float(existing.get("time_match") or 0.0), time_match)
                        existing["place_match"] = max(float(existing.get("place_match") or 0.0), place_match)
                        existing["fusion_match"] = max(float(existing.get("fusion_match") or 0.0), hint_score)
                        hybrid_debug = dict(existing.get("hybrid_debug") or {})
                        hybrid_debug["repo_hint_match"] = {
                            "entity_match": round(entity_match, 4),
                            "predicate_match": round(predicate_match, 4),
                            "time_match": round(time_match, 4),
                            "place_match": round(place_match, 4),
                            "hint_score": round(hint_score, 4),
                        }
                        existing["hybrid_debug"] = hybrid_debug
                        continue
                    assertion_hits.append(
                        {
                            "id": row_id,
                            "kb_uuid": kb.uuid,
                            "point_type": "assertion",
                            "source_point_id": row.get("source_point_id"),
                            "source_sentence_id": row.get("source_sentence_id"),
                            "text": row.get("canonical_text") or "",
                            "semantic_match": 0.0,
                            "lexical_match": 0.0,
                            "fusion_match": hint_score,
                            "hybrid_debug": {
                                "repo_hint_match": {
                                    "entity_match": round(entity_match, 4),
                                    "predicate_match": round(predicate_match, 4),
                                    "time_match": round(time_match, 4),
                                    "place_match": round(place_match, 4),
                                    "hint_score": round(hint_score, 4),
                                }
                            },
                            "entity_match": entity_match,
                            "time_match": time_match,
                            "place_match": place_match,
                            "predicate_match": predicate_match,
                            "graph_proximity": 0.0,
                            "strength": float(row.get("strength") or 0.0),
                            "baseline_strength": float(row.get("baseline_strength") or 0.05),
                            "decay_rate": float(row.get("decay_rate") or 0.015),
                            "last_reinforced_at": row.get("last_reinforced_at"),
                            "confidence": float(row.get("confidence") or 0.0),
                            "source_time": row.get("source_time"),
                            "ingest_time": row.get("ingest_time"),
                            "status": str(row.get("status") or "active").lower(),
                            "predicate": row.get("predicate"),
                            "entity_ids": candidate_entity_ids,
                            "place_ids": [int(row.get("place_id"))] if row.get("place_id") is not None else [],
                            "place_keys": _row_place_keys(row),
                            "place_hierarchy_keys": place_hierarchy_keys,
                            "valid_time_from": row.get("valid_time_from") or row.get("time_from"),
                            "valid_time_to": row.get("valid_time_to") or row.get("time_to"),
                            "time_from": row.get("valid_time_from") or row.get("time_from"),
                            "time_to": row.get("valid_time_to") or row.get("time_to"),
                            "relation_weight": 0.0,
                            "relation_confidence": 0.0,
                            "relation_depth": None,
                            "is_seed": True,
                        }
                    )

        # Relation-alapú local neighborhood expansion seed assertionökből.
        assertion_seeds_by_kb: dict[str, list[int]] = {}
        for row in sorted(assertion_hits, key=lambda x: float(x.get("semantic_match") or 0.0), reverse=True):
            kb_uuid_seed = str(row.get("kb_uuid") or "")
            aid = _parse_assertion_id(row.get("id"))
            if not kb_uuid_seed or aid is None:
                continue
            assertion_seeds_by_kb.setdefault(kb_uuid_seed, [])
            if aid not in assertion_seeds_by_kb[kb_uuid_seed] and len(assertion_seeds_by_kb[kb_uuid_seed]) < 6:
                assertion_seeds_by_kb[kb_uuid_seed].append(aid)

        for kb in scoped_kbs:
            if kb.id is None:
                continue
            kb_place_resolved_keys = set(resolved_places_by_kb.get(kb.uuid) or [])
            kb_place_hierarchy_keys = set(resolved_place_hierarchy_by_kb.get(kb.uuid) or [])
            seed_ids = assertion_seeds_by_kb.get(kb.uuid) or []
            if not seed_ids:
                continue
            t_db = perf_counter()
            neighbors = self.repo.get_assertion_neighbors(
                kb_id=kb.id,
                assertion_ids=seed_ids,
                max_hops=max(1, int(getattr(settings, "kb_max_relation_hops", 2) or 2)),
                allowed_relation_types=[
                    "SUPPORTS",
                    "REFINES",
                    "GENERALIZES",
                    "CONTRADICTS",
                    "TEMPORALLY_SPLITS",
                    "SAME_SUBJECT",
                    "SAME_OBJECT",
                    "SAME_PREDICATE",
                    "SAME_PLACE",
                    "SAME_SOURCE_POINT",
                    "TEMPORALLY_OVERLAPS",
                ],
                limit=24,
            )
            db_latency_ms += (perf_counter() - t_db) * 1000.0
            for row in neighbors:
                assertion_hits.append(
                    {
                        "id": f"assertion-{row.get('assertion_id')}",
                        "kb_uuid": kb.uuid,
                        "point_type": "assertion",
                        "source_point_id": row.get("source_point_id"),
                        "source_sentence_id": None,
                        "text": row.get("canonical_text") or "",
                        "semantic_match": 0.45,
                        "lexical_match": 0.0,
                        "fusion_match": 0.45,
                        "entity_match": 0.0,
                        "time_match": compute_time_overlap_score(
                            query_from=query_valid_time_from,
                            query_to=query_valid_time_to,
                            item_from=row.get("valid_time_from") or row.get("time_from"),
                            item_to=row.get("valid_time_to") or row.get("time_to"),
                        ),
                        "place_match": self._compute_place_match(
                            query_terms=place_terms,
                            resolved_keys=kb_place_resolved_keys,
                            hierarchy_keys=kb_place_hierarchy_keys,
                            item_place_keys=[row.get("place_key")] if row.get("place_key") else [],
                            item_place_hierarchy_keys=row.get("place_hierarchy_keys") or [],
                        ),
                        "predicate_match": 1.0 if row.get("predicate") and row.get("predicate") in predicate_terms else 0.0,
                        "graph_proximity": min(
                            1.0,
                            float(row.get("relation_graph_score") or 0.0)
                            if row.get("relation_graph_score") is not None
                            else (
                                float(row.get("relation_current_weight") or row.get("relation_weight") or 0.0)
                                * (0.35 + (0.65 * float(row.get("relation_confidence") or 0.0)))
                                * _relation_type_proximity_factor(row.get("relation_type"))
                                * (0.85 if int(row.get("depth") or 1) > 1 else 1.0)
                            ),
                        ),
                        "strength": float(row.get("strength") or 0.0),
                        "baseline_strength": float(row.get("baseline_strength") or 0.05),
                        "decay_rate": float(row.get("decay_rate") or 0.015),
                        "last_reinforced_at": row.get("last_reinforced_at"),
                        "confidence": float(row.get("confidence") or 0.0),
                        "source_time": row.get("source_time"),
                        "ingest_time": row.get("ingest_time"),
                        "time_semantics": {
                            "valid_time": {
                                "from": _iso_or_none(row.get("valid_time_from") or row.get("time_from")),
                                "to": _iso_or_none(row.get("valid_time_to") or row.get("time_to")),
                            },
                            "source_time": _iso_or_none(row.get("source_time")),
                            "ingest_time": _iso_or_none(row.get("ingest_time")),
                        },
                        "status": str(row.get("status") or "active").lower(),
                        "predicate": row.get("predicate"),
                        "entity_ids": [x for x in [row.get("subject_entity_id"), row.get("object_entity_id")] if x],
                        "place_ids": [int(row.get("place_id"))] if row.get("place_id") is not None else [],
                        "place_keys": [row.get("place_key")] if row.get("place_key") else [],
                        "place_hierarchy_keys": row.get("place_hierarchy_keys") or [],
                        "valid_time_from": row.get("valid_time_from") or row.get("time_from"),
                        "valid_time_to": row.get("valid_time_to") or row.get("time_to"),
                        "time_from": row.get("valid_time_from") or row.get("time_from"),
                        "time_to": row.get("valid_time_to") or row.get("time_to"),
                        "relation_type": row.get("relation_type"),
                        "relation_weight": float(row.get("relation_current_weight") or row.get("relation_weight") or 0.0),
                        "relation_confidence": float(row.get("relation_confidence") or 0.0),
                        "relation_depth": int(row.get("depth") or 1),
                        "is_seed": False,
                    }
                )

        # Lokális bővítés: top source_point környezetéből plusz mondatok/chunkok.
        seed_source_points = [
            x.get("source_point_id")
            for x in assertion_hits[:4]
            if x.get("source_point_id")
        ]
        unique_seed_points = list(dict.fromkeys(seed_source_points))
        if unique_seed_points and retrieval_mode in {"assertion_first", "entity_first", "timeline_first", "comparison_first"}:
            for kb in scoped_kbs:
                kb_place_resolved_keys = set(resolved_places_by_kb.get(kb.uuid) or [])
                kb_place_hierarchy_keys = set(resolved_place_hierarchy_by_kb.get(kb.uuid) or [])
                for source_point_id in unique_seed_points:
                    for point_type, target in [("sentence", sentence_hits)]:
                        expanded = await _cached_search(
                            kb=kb,
                            query_value=lexical_query_text,
                            lexical_query_value=lexical_query_text,
                            point_type=point_type,
                            limit_value=3,
                            payload_filter_value={
                                "kb_uuid": kb.uuid,
                                "source_point_id": source_point_id,
                            },
                            fusion_semantic_weight_value=(0.46 if point_type == "sentence" else 0.40),
                            fusion_lexical_weight_value=(0.54 if point_type == "sentence" else 0.60),
                            lexical_focus_terms_value=lexical_focus_terms,
                            exact_phrases_value=exact_phrase_candidates,
                            rare_terms_value=rare_entity_terms,
                        )
                        for hit in expanded:
                            payload = dict(hit.get("payload") or {})
                            text = str(payload.get("text") or "").strip()
                            if not text:
                                continue
                            target.append(
                                {
                                    "id": hit.get("id"),
                                    "kb_uuid": kb.uuid,
                                    "point_type": point_type,
                                    "source_point_id": payload.get("source_point_id"),
                                    "source_sentence_id": payload.get("source_sentence_id"),
                                    "text": text,
                                    "semantic_match": float(hit.get("semantic_score_norm") or hit.get("semantic_score") or hit.get("score") or 0.0),
                                    "lexical_match": float(hit.get("lexical_score_norm") or hit.get("lexical_score") or 0.0),
                                    "fusion_match": float(hit.get("fusion_score") or 0.0),
                                    "hybrid_debug": hit.get("fusion_debug") or {},
                                    "entity_match": 0.0,
                                    "time_match": 0.0,
                                    "place_match": self._compute_place_match(
                                        query_terms=place_terms,
                                        resolved_keys=kb_place_resolved_keys,
                                        hierarchy_keys=kb_place_hierarchy_keys,
                                        item_place_keys=payload.get("place_keys")
                                        or ([payload.get("place_key")] if payload.get("place_key") else []),
                                        item_place_hierarchy_keys=payload.get("place_hierarchy_keys") or [],
                                    ),
                                    "predicate_match": 0.0,
                                    "graph_proximity": 0.5,
                                    "strength": float(payload.get("strength") or 0.0),
                                    "confidence": float(payload.get("confidence") or 0.0),
                                    "source_time": payload.get("source_time"),
                                    "ingest_time": payload.get("ingest_time"),
                                    "time_semantics": {
                                        "valid_time": {
                                            "from": _iso_or_none(payload.get("valid_time_from") or payload.get("time_from")),
                                            "to": _iso_or_none(payload.get("valid_time_to") or payload.get("time_to")),
                                        },
                                        "source_time": _iso_or_none(payload.get("source_time")),
                                        "ingest_time": _iso_or_none(payload.get("ingest_time")),
                                    },
                                    "predicate": payload.get("predicate"),
                                    "entity_ids": payload.get("entity_ids") or [],
                                    "place_ids": payload.get("place_ids") or [],
                                    "place_keys": payload.get("place_keys") or ([payload.get("place_key")] if payload.get("place_key") else []),
                                    "place_hierarchy_keys": payload.get("place_hierarchy_keys") or [],
                                    "valid_time_from": payload.get("valid_time_from") or payload.get("time_from"),
                                    "valid_time_to": payload.get("valid_time_to") or payload.get("time_to"),
                                    "time_from": payload.get("valid_time_from") or payload.get("time_from"),
                                    "time_to": payload.get("valid_time_to") or payload.get("time_to"),
                                }
                            )
                    if retrieval_mode == "chunk_fallback":
                        expanded_chunks = await _cached_search(
                            kb=kb,
                            query_value=lexical_query_text,
                            lexical_query_value=lexical_query_text,
                            point_type="structural_chunk",
                            limit_value=2,
                            payload_filter_value={
                                "kb_uuid": kb.uuid,
                                "source_point_id": source_point_id,
                            },
                            fusion_semantic_weight_value=0.40,
                            fusion_lexical_weight_value=0.60,
                            lexical_focus_terms_value=lexical_focus_terms,
                            exact_phrases_value=exact_phrase_candidates,
                            rare_terms_value=rare_entity_terms,
                        )
                        for hit in expanded_chunks:
                            payload = dict(hit.get("payload") or {})
                            text = str(payload.get("text") or "").strip()
                            if not text:
                                continue
                            chunk_hits.append(
                                {
                                    "id": hit.get("id"),
                                    "kb_uuid": kb.uuid,
                                    "point_type": "structural_chunk",
                                    "source_point_id": payload.get("source_point_id"),
                                    "source_sentence_id": payload.get("source_sentence_id"),
                                    "text": text,
                                    "semantic_match": float(hit.get("semantic_score_norm") or hit.get("semantic_score") or hit.get("score") or 0.0),
                                    "lexical_match": float(hit.get("lexical_score_norm") or hit.get("lexical_score") or 0.0),
                                    "fusion_match": float(hit.get("fusion_score") or 0.0),
                                    "hybrid_debug": hit.get("fusion_debug") or {},
                                    "entity_match": 0.0,
                                    "time_match": 0.0,
                                    "place_match": self._compute_place_match(
                                        query_terms=place_terms,
                                        resolved_keys=kb_place_resolved_keys,
                                        hierarchy_keys=kb_place_hierarchy_keys,
                                        item_place_keys=payload.get("place_keys")
                                        or ([payload.get("place_key")] if payload.get("place_key") else []),
                                        item_place_hierarchy_keys=payload.get("place_hierarchy_keys") or [],
                                    ),
                                    "predicate_match": 0.0,
                                    "graph_proximity": 0.5,
                                    "strength": float(payload.get("strength") or 0.0),
                                    "confidence": float(payload.get("confidence") or 0.0),
                                    "source_time": payload.get("source_time"),
                                    "ingest_time": payload.get("ingest_time"),
                                    "time_semantics": {
                                        "valid_time": {
                                            "from": _iso_or_none(payload.get("valid_time_from") or payload.get("time_from")),
                                            "to": _iso_or_none(payload.get("valid_time_to") or payload.get("time_to")),
                                        },
                                        "source_time": _iso_or_none(payload.get("source_time")),
                                        "ingest_time": _iso_or_none(payload.get("ingest_time")),
                                    },
                                    "predicate": payload.get("predicate"),
                                    "entity_ids": payload.get("entity_ids") or [],
                                    "place_ids": payload.get("place_ids") or [],
                                    "place_keys": payload.get("place_keys") or ([payload.get("place_key")] if payload.get("place_key") else []),
                                    "place_hierarchy_keys": payload.get("place_hierarchy_keys") or [],
                                    "valid_time_from": payload.get("valid_time_from") or payload.get("time_from"),
                                    "valid_time_to": payload.get("valid_time_to") or payload.get("time_to"),
                                    "time_from": payload.get("valid_time_from") or payload.get("time_from"),
                                    "time_to": payload.get("valid_time_to") or payload.get("time_to"),
                                }
                            )

        source_counts = Counter(
            [x.get("source_point_id") for x in (assertion_hits + sentence_hits + chunk_hits) if x.get("source_point_id")]
        )
        predicate_counts = Counter(
            [str(x.get("predicate")).lower() for x in assertion_hits if x.get("predicate")]
        )
        entity_counts = Counter(
            [int(eid) for row in (assertion_hits + sentence_hits + chunk_hits) for eid in (row.get("entity_ids") or []) if isinstance(eid, int)]
        )

        for row in assertion_hits + sentence_hits + chunk_hits:
            source_point = row.get("source_point_id")
            existing_graph = float(row.get("graph_proximity", 0.0))
            if source_point:
                row["graph_proximity"] = max(existing_graph, min(1.0, 0.2 + 0.2 * max(0, source_counts[source_point] - 1)))
            pred = str(row.get("predicate") or "").lower().strip()
            if pred and predicate_counts.get(pred, 0) > 1:
                row["graph_proximity"] = min(1.0, float(row.get("graph_proximity", 0.0)) + 0.2)
            if any(entity_counts.get(int(eid), 0) > 1 for eid in (row.get("entity_ids") or []) if isinstance(eid, int)):
                row["graph_proximity"] = min(1.0, float(row.get("graph_proximity", 0.0)) + 0.2)

        min_conf = float(getattr(settings, "kb_min_confidence", 0.2) or 0.2)
        min_strength = float(getattr(settings, "kb_min_current_strength", 0.03) or 0.03)
        filtered_assertion_hits: list[dict] = []
        for row in assertion_hits:
            status = str(row.get("status") or "active").lower()
            if status in {"conflicted", "refined", "active"}:
                filtered_assertion_hits.append(row)
                continue
            current_strength = compute_current_strength(
                strength=float(row.get("strength") or 0.05),
                baseline_strength=float(row.get("baseline_strength") or 0.05),
                decay_rate=float(row.get("decay_rate") or 0.015),
                last_reinforced_at=row.get("last_reinforced_at"),
            )
            if float(row.get("confidence") or 0.0) >= min_conf and current_strength >= min_strength:
                filtered_assertion_hits.append(row)
        if filtered_assertion_hits:
            assertion_hits = filtered_assertion_hits

        t_context = perf_counter()
        packet = self.context_builder.build_context_packet(
            assertion_hits=assertion_hits,
            sentence_hits=sentence_hits,
            chunk_hits=chunk_hits,
            related_entities=list({(x["kb_uuid"], x["entity_id"]): x for x in related_entities}.values()),
            query_focus={
                "raw_query": parsed_query.get("raw_query", question),
                "intent": parsed_query.get("intent"),
                "entity_candidates": parsed_query.get("entity_candidates", []),
                "resolved_entity_candidates": parsed_query.get("resolved_entity_candidates", {}),
                "focus_axes": parsed_query.get("focus_axes") or {},
                "parser_audit": parsed_query.get("parser_audit") or {},
                "parse_time_ms": float(parsed_query.get("parse_time_ms") or 0.0),
                "valid_time_window": parsed_query.get("valid_time_window") or query_valid_time_window,
                "time_window": parsed_query.get("time_window") or query_valid_time_window,
                "place_candidates": parsed_query.get("place_candidates", []),
                "resolved_place_candidates": parsed_query.get("resolved_place_candidates", {}),
                "resolved_place_hierarchy_keys": parsed_query.get("resolved_place_hierarchy_keys", {}),
                "attribute_candidates": parsed_query.get("attribute_candidates", []),
                "relation_candidates": parsed_query.get("relation_candidates", []),
                "normalized_query_text": parsed_query.get("normalized_query_text", query_text),
                "lexical_query_text": parsed_query.get("lexical_query_text", lexical_query_text),
                "query_embedding_text": parsed_query.get("query_embedding_text", query_text),
                "comparison_targets": parsed_query.get("comparison_targets", []),
                "comparison_time_windows": parsed_query.get("comparison_time_windows", []),
                "retrieval_mode": retrieval_mode,
            },
            top_n=10,
        )
        context_build_ms = (perf_counter() - t_context) * 1000.0
        if retrieval_mode == "timeline_first":
            packet["expanded_assertions"] = sorted(
                packet.get("expanded_assertions") or [],
                key=lambda x: str(_valid_time_from_value(x) or _valid_time_to_value(x) or ""),
            )
            packet["timeline_sequence"] = [
                {
                    "assertion_id": x.get("id"),
                    "valid_time_from": _valid_time_from_value(x),
                    "valid_time_to": _valid_time_to_value(x),
                    "time_from": _valid_time_from_value(x),
                    "time_to": _valid_time_to_value(x),
                    "text": x.get("text"),
                }
                for x in packet.get("top_assertions") or []
            ]

        if retrieval_mode == "comparison_first":
            targets = parsed_query.get("comparison_targets") or []
            left_term = str(targets[0]).lower() if len(targets) > 0 else ""
            right_term = str(targets[1]).lower() if len(targets) > 1 else ""
            comparison_left = []
            comparison_right = []
            for row in packet.get("top_assertions") or []:
                text_low = str(row.get("text") or "").lower()
                if left_term and left_term in text_low:
                    comparison_left.append(row)
                elif right_term and right_term in text_low:
                    comparison_right.append(row)
            packet["comparison_left"] = comparison_left
            packet["comparison_right"] = comparison_right
            packet["comparison_summary"] = {
                "left_count": len(comparison_left),
                "right_count": len(comparison_right),
                "left_target": targets[0] if len(targets) > 0 else None,
                "right_target": targets[1] if len(targets) > 1 else None,
            }

        primary_assertions = list(packet.get("seed_assertions") or packet.get("top_assertions") or [])
        primary_assertions.sort(key=_assertion_context_rank)
        primary_assertions = primary_assertions[:6]
        primary_ids = {
            aid for aid in (_parse_assertion_id(row.get("id")) for row in primary_assertions)
            if isinstance(aid, int)
        }
        supporting_assertions = [
            row
            for row in (packet.get("expanded_assertions") or packet.get("top_assertions") or [])
            if (_parse_assertion_id(row.get("id")) not in primary_ids)
        ]
        supporting_assertions.sort(key=_assertion_context_rank)
        supporting_assertions = supporting_assertions[:8]
        supporting_ids = {
            aid for aid in (_parse_assertion_id(row.get("id")) for row in supporting_assertions)
            if isinstance(aid, int)
        }
        packet["primary_assertions"] = primary_assertions
        packet["supporting_assertions"] = supporting_assertions
        packet["top_assertions"] = primary_assertions + [
            row for row in (packet.get("top_assertions") or [])
            if _parse_assertion_id(row.get("id")) not in primary_ids
        ]

        resolved_query_place_keys = _dedupe_keep_order(
            list(place_terms)
            + [
                _normalize_place_key(str(value))
                for values in (parsed_query.get("resolved_place_candidates", {}) or {}).values()
                for value in (values or [])
                if _normalize_place_key(str(value))
            ]
        )
        packet["related_places"] = self._build_related_places(
            packet=packet,
            query_place_keys=resolved_query_place_keys,
        )
        packet["place_context"] = {
            "query_place_candidates": place_terms,
            "resolved_place_candidates": parsed_query.get("resolved_place_candidates", {}),
            "resolved_place_hierarchy_keys": parsed_query.get("resolved_place_hierarchy_keys", {}),
            "related_places": packet.get("related_places") or [],
        }
        top_assertion_ids = [
            _parse_assertion_id(x.get("id"))
            for x in (packet.get("top_assertions") or [])
        ]
        top_assertion_ids = [x for x in top_assertion_ids if isinstance(x, int)]
        if top_assertion_ids:
            t_db = perf_counter()
            evidence_rows = self.repo.list_evidence_sentences(top_assertion_ids, limit=60)
            db_latency_ms += (perf_counter() - t_db) * 1000.0
            if not isinstance(evidence_rows, list):
                evidence_rows = []
            if evidence_rows:
                max_ev_per_assertion = max(1, int(getattr(settings, "kb_context_max_evidence_per_assertion", 2) or 2))
                ev_bucket: dict[int, list[dict]] = {}
                for row in evidence_rows:
                    aid = int(row.get("assertion_id") or 0)
                    if aid <= 0:
                        continue
                    ev_bucket.setdefault(aid, [])
                    if len(ev_bucket[aid]) < max_ev_per_assertion:
                        ev_bucket[aid].append(row)
                evidence_rows = [r for rows in ev_bucket.values() for r in rows]
                evidence_sentence_ids = [int(x["sentence_id"]) for x in evidence_rows if x.get("sentence_id") is not None]
                t_db = perf_counter()
                source_chunks = self.repo.list_chunks_for_sentence_ids(evidence_sentence_ids, limit=10)
                db_latency_ms += (perf_counter() - t_db) * 1000.0
                if not isinstance(source_chunks, list):
                    source_chunks = []
                # Assertion-first packet: evidence és chunkok ezekből épülnek.
                for row in evidence_rows:
                    aid = int(row.get("assertion_id") or 0)
                    row["context_role"] = "primary_evidence" if aid in primary_ids else (
                        "supporting_evidence" if aid in supporting_ids else "evidence"
                    )
                evidence_rows.sort(key=lambda row: _evidence_context_rank(row, primary_ids, supporting_ids))
                for row in source_chunks:
                    linked_ids = {int(x) for x in (row.get("assertion_ids") or []) if isinstance(x, int)}
                    row["context_role"] = "primary_chunk" if linked_ids.intersection(primary_ids) else (
                        "supporting_chunk" if linked_ids.intersection(supporting_ids) else "context_chunk"
                    )
                source_chunks.sort(key=lambda row: _chunk_context_rank(row, primary_ids, supporting_ids))
                packet["evidence_sentences"] = evidence_rows
                packet["source_chunks"] = source_chunks
                evidence_ids_by_assertion: dict[int, list[int]] = {}
                source_points_by_assertion: dict[int, list[str]] = {}
                for row in evidence_rows:
                    aid = int(row.get("assertion_id"))
                    sid = int(row.get("sentence_id"))
                    evidence_ids_by_assertion.setdefault(aid, []).append(sid)
                    source_points_by_assertion.setdefault(aid, [])
                    sp = str(row.get("source_point_id") or "")
                    if sp and sp not in source_points_by_assertion[aid]:
                        source_points_by_assertion[aid].append(sp)
                mention_map = self.repo.list_mentions_for_assertions(top_assertion_ids)
                if not isinstance(mention_map, dict):
                    mention_map = {}
                for row in packet.get("top_assertions") or []:
                    aid = _parse_assertion_id(row.get("id"))
                    if aid is None:
                        continue
                    row["evidence_sentence_ids"] = evidence_ids_by_assertion.get(aid, [])
                    row["evidence_source_point_ids"] = source_points_by_assertion.get(aid, [])
                    row["mentions"] = mention_map.get(aid, [])
                packet["assertion_mention_traces"] = [
                    {
                        "assertion_id": row.get("id"),
                        "seed_role": "seed" if any(str(seed.get("id")) == str(row.get("id")) for seed in (packet.get("seed_assertions") or [])) else "expanded",
                        "sentence_ids": row.get("evidence_sentence_ids") or [],
                        "source_point_ids": row.get("evidence_source_point_ids") or [],
                        "mention_ids": [m.get("id") for m in (row.get("mentions") or []) if m.get("id") is not None],
                        "entity_ids": row.get("entity_ids") or [],
                        "mentions": row.get("mentions") or [],
                    }
                    for row in (packet.get("top_assertions") or [])
                ]
        packet["related_places"] = self._build_related_places(
            packet=packet,
            query_place_keys=resolved_query_place_keys,
        )
        packet["place_context"] = {
            "query_place_candidates": place_terms,
            "resolved_place_candidates": parsed_query.get("resolved_place_candidates", {}),
            "resolved_place_hierarchy_keys": parsed_query.get("resolved_place_hierarchy_keys", {}),
            "related_places": packet.get("related_places") or [],
        }

        packet["scoring_summary"] = {
            **(packet.get("scoring_summary") or {}),
            "kb_count": len(scoped_kbs),
            "kb_uuids": [x.uuid for x in scoped_kbs],
            "entity_candidates": parsed_query.get("entity_candidates", []),
            "place_candidates": parsed_query.get("place_candidates", []),
            "resolved_place_candidates": parsed_query.get("resolved_place_candidates", {}),
            "resolved_place_hierarchy_keys": parsed_query.get("resolved_place_hierarchy_keys", {}),
            "related_places": packet.get("related_places") or [],
            "time_candidates": parsed_query.get("time_candidates", []),
            "valid_time_window": parsed_query.get("valid_time_window") or query_valid_time_window,
            "time_window": parsed_query.get("time_window") or query_valid_time_window,
            "predicate_candidates": parsed_query.get("predicate_candidates", []),
            "attribute_candidates": parsed_query.get("attribute_candidates", []),
            "relation_candidates": parsed_query.get("relation_candidates", []),
            "intent": parsed_query.get("intent"),
            "retrieval_mode": retrieval_mode,
            "hybrid_recall_enabled": True,
            "query_embedding_reuse": bool(
                int(parsed_query.get("query_embedding_generation_count") or 0) <= 1
            ),
            "query_embedding_vector_ready": request_query_vector is not None,
            "query_embedding_time_ms": float(parsed_query.get("query_embedding_time_ms") or 0.0),
            "qdrant_request_cache_entries": len(qdrant_search_cache),
            "qdrant_search_calls": qdrant_search_calls,
            "qdrant_precomputed_vector_calls": qdrant_precomputed_vector_calls,
            "query_embedding_reuse_verified": bool(
                int(parsed_query.get("query_embedding_generation_count") or 0) <= 1
                and (qdrant_search_calls == 0 or qdrant_search_calls == qdrant_precomputed_vector_calls)
            ),
            "query_embedding_generation_count": int(parsed_query.get("query_embedding_generation_count") or 0),
            "query_embedding_prepare_calls": int(parsed_query.get("query_embedding_prepare_calls") or 0),
            "latency_ms": {
                "parse": round(float(parsed_query.get("parse_time_ms") or 0.0), 2),
                "query_embedding": round(float(parsed_query.get("query_embedding_time_ms") or 0.0), 2),
                "qdrant_recall": round(qdrant_latency_ms, 2),
                "db_expansion": round(db_latency_ms, 2),
                "rerank": round(float(((packet.get("scoring_summary") or {}).get("timing_ms") or {}).get("rerank") or 0.0), 2),
                "context_build": round(context_build_ms, 2),
            },
            "time_semantics": {
                "query_valid_time_window": query_valid_time_window,
                "time_slice_grouping_axis": "valid_time",
                "top_assertion_times": [
                    {
                        "assertion_id": row.get("id"),
                        **_time_semantics_debug(row),
                    }
                    for row in (packet.get("top_assertions") or [])[:8]
                ],
            },
            "place_semantics": {
                "query_place_candidates": place_terms,
                "resolved_place_candidates": parsed_query.get("resolved_place_candidates", {}),
                "resolved_place_hierarchy_keys": parsed_query.get("resolved_place_hierarchy_keys", {}),
                "top_place_context": (packet.get("related_places") or [])[:8],
            },
            "context_layers": {
                "primary_assertion_ids": [row.get("id") for row in (packet.get("primary_assertions") or [])],
                "supporting_assertion_ids": [row.get("id") for row in (packet.get("supporting_assertions") or [])],
                "evidence_sentence_ids": [
                    row.get("sentence_id")
                    for row in (packet.get("evidence_sentences") or [])
                ],
                "chunk_ids": [
                    row.get("chunk_id") or row.get("id")
                    for row in (packet.get("source_chunks") or [])
                ],
                "assertion_first": True,
                "chunk_role": "evidence_fallback_context",
            },
        }
        packet["context_layers"] = {
            "primary_assertions": [
                {
                    "id": row.get("id"),
                    "text": row.get("text") or row.get("canonical_text"),
                    "entity_match": row.get("entity_match"),
                    "time_match": row.get("time_match"),
                    "place_match": row.get("place_match"),
                    "relation_confidence": row.get("relation_confidence"),
                    "strength": row.get("strength"),
                    "confidence": row.get("confidence"),
                }
                for row in (packet.get("primary_assertions") or [])
            ],
            "supporting_assertions": [
                {
                    "id": row.get("id"),
                    "text": row.get("text") or row.get("canonical_text"),
                    "entity_match": row.get("entity_match"),
                    "time_match": row.get("time_match"),
                    "place_match": row.get("place_match"),
                    "relation_confidence": row.get("relation_confidence"),
                    "strength": row.get("strength"),
                    "confidence": row.get("confidence"),
                }
                for row in (packet.get("supporting_assertions") or [])
            ],
            "evidence_sentences": [
                {
                    "sentence_id": row.get("sentence_id"),
                    "assertion_id": row.get("assertion_id"),
                    "context_role": row.get("context_role") or "evidence",
                    "text": row.get("text"),
                }
                for row in (packet.get("evidence_sentences") or [])
            ],
            "context_chunks": [
                {
                    "chunk_id": row.get("chunk_id") or row.get("id"),
                    "context_role": row.get("context_role") or "context_chunk",
                    "assertion_ids": row.get("assertion_ids") or [],
                    "text": row.get("text"),
                }
                for row in (packet.get("source_chunks") or [])
            ],
        }
        # Related entity summary: id helyett emberi olvasható összegzés.
        related_entity_ids: dict[int, int] = {}
        for row in packet.get("top_assertions") or []:
            for eid in row.get("entity_ids") or []:
                if isinstance(eid, int):
                    related_entity_ids[eid] = related_entity_ids.get(eid, 0) + 1
        existing_related_entities = {
            (int(x.get("entity_id")), str(x.get("kb_uuid") or "")): x
            for x in (packet.get("related_entities") or [])
            if isinstance(x.get("entity_id"), int)
        }
        resolved_related_entities: list[dict] = []
        for kb in scoped_kbs:
            if kb.id is None:
                continue
            entity_rows = self.repo.get_entities_by_ids(kb.id, list(related_entity_ids.keys()))
            for e in entity_rows:
                eid = int(e["id"])
                existing = existing_related_entities.get((eid, kb.uuid), {})
                resolved_related_entities.append(
                    {
                        "entity_id": eid,
                        "kb_uuid": kb.uuid,
                        "canonical_name": e.get("canonical_name"),
                        "entity_type": e.get("entity_type"),
                        "aliases": e.get("aliases") or [],
                        "assertion_ids": existing.get("assertion_ids") or [],
                        "seed_assertion_ids": existing.get("seed_assertion_ids") or [],
                        "expanded_assertion_ids": existing.get("expanded_assertion_ids") or [],
                        "source_point_ids": existing.get("source_point_ids") or [],
                        "top_predicates": existing.get("top_predicates") or [],
                        "mention_count_in_context": int(existing.get("mention_count_in_context") or related_entity_ids.get(eid, 0)),
                    }
                )
        if resolved_related_entities:
            packet["related_entities"] = resolved_related_entities
            packet["primary_entities"] = resolved_related_entities[:5]
        # Top assertionök enyhe retrieval-hit megerősítést kapnak (best effort).
        for row in packet.get("top_assertions") or []:
            assertion_id = _parse_assertion_id(row.get("id"))
            assertion_kb_uuid = str(row.get("kb_uuid") or "").strip()
            if assertion_id is None or not assertion_kb_uuid:
                continue
            try:
                self.reinforce_assertion(
                    kb_uuid=assertion_kb_uuid,
                    assertion_id=assertion_id,
                    event_type="CHAT_RETRIEVAL_HIT",
                )
            except Exception:
                pass
        total_ms = (perf_counter() - t_total_start) * 1000.0
        packet["scoring_summary"]["latency_ms"]["total"] = round(total_ms, 2)
        return packet

    # ------------------------------------------------------------
    #  FILE TRAINING
    # ------------------------------------------------------------
    async def train_from_file(
        self,
        uuid: str,
        file,
        idempotency_key: Optional[str] = None,
        current_user_id: Optional[int] = None,
        confirm_pii: bool = False,
        pii_review_decision: Optional[str] = None,
        pii_decisions: Optional[List[dict]] = None,
    ) -> dict[str, Any]:
        kb = self.repo.get_by_uuid(uuid)
        if not kb:
            raise ValueError("KB not found")

        filename = (getattr(file, "filename", None) or "").strip() or ""
        file_like = getattr(file, "file", file)
        try:
            result: ExtractedFileResult = extract_file(file_like, filename)
        except ValueError as e:
            raise e

        if result.status == STATUS_EMPTY:
            return {
                "status": "empty",
                "message": "A fájl tartalma üres, nincs betölthető szöveg.",
                "metadata": _metadata_for_response(result.metadata),
            }

        if result.status == STATUS_SCANNED_REVIEW_REQUIRED:
            return {
                "status": "scanned_review_required",
                "message": "A dokumentum valószínűleg szkennelt; OCR vagy manuális ellenőrzés ajánlott.",
                "metadata": _metadata_for_response(result.metadata),
            }

        # Layer: extracted text → sanitized (PII) and stored via add_block
        title = result.metadata.filename or filename or "document"
        if result.metadata.author:
            title = f"{title} (szerző: {result.metadata.author})"
        return await self.add_block(
            uuid,
            title,
            result.extracted_text,
            idempotency_key=idempotency_key,
            current_user_id=current_user_id,
            confirm_pii=confirm_pii,
            pii_review_decision=pii_review_decision,
            pii_decisions=pii_decisions,
        )
