from __future__ import annotations

import json
import uuid as uuid_lib
from typing import List, Optional, Any
from apps.knowledge.ports.repositories import KnowledgeBaseRepositoryPort, KbPermissionItem
from apps.knowledge.domain.kb import KnowledgeBase
from apps.knowledge.application.pii_filter import (
    filter_pii,
    apply_pii_replacements,
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


class KnowledgeBaseService:

    def __init__(
        self,
        repo: KnowledgeBaseRepositoryPort,
        qdrant_service: "QdrantClientWrapper",
        user_repo: Any = None,
    ) -> None:
        self.repo = repo
        self.qdrant = qdrant_service
        self.user_repo = user_repo

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
        personal_data_sensitivity: Optional[str] = None,
    ) -> KnowledgeBase:
        """Knowledge base frissítése (név, leírás, személyes adatok beállításai)."""
        kb = self.repo.get_by_uuid(uuid)
        if not kb:
            raise ValueError("KB not found")

        kb.name = name
        kb.description = description
        if personal_data_mode is not None:
            kb.personal_data_mode = personal_data_mode
        if personal_data_sensitivity is not None:
            kb.personal_data_sensitivity = personal_data_sensitivity
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

        masked = False
        if matches:
            if mode == PERSONAL_DATA_MODE_NO:
                # Automatikus törlés: "..."-ra cseréljük, nem tároljuk personal_data-ban
                content_to_store = apply_pii_replacements(
                    raw, matches, [""] * len(matches), mode="remove"
                )
            elif decisions_list:
                # with_confirmation + soronkénti döntések
                content_to_store, mask_indices = apply_pii_replacements_with_decisions(
                    raw, matches, decisions_list
                )
                for i in mask_indices:
                    m = matches[i]
                    self.repo.add_personal_data(kb.id, m[2], m[3])
                masked = len(mask_indices) > 0
            else:
                # allowed_not_to_ai vagy with_confirmation (régi flow): maszkolás mind
                ref_ids = [
                    self.repo.add_personal_data(kb.id, m[2], m[3])
                    for m in matches
                ]
                content_to_store = apply_pii_replacements(
                    raw, matches, ref_ids, mode=sanitize_mode or "mask"
                )
                masked = True
        else:
            content_to_store = raw

        user_display = ""
        if current_user_id and self.user_repo:
            u = self.user_repo.get_by_id(current_user_id)
            if u:
                user_display = (getattr(u, "name", None) or "").strip() or getattr(u, "email", "") or ""

        display_title = (title or "").strip()
        point_id = str(uuid_lib.uuid4())
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
            raw_content=raw if matches else None,
            review_decision=decision,
        )
        pii_replaced_with_dots = bool(matches and mode == PERSONAL_DATA_MODE_NO)
        return {"status": "ok", "masked": masked, "pii_replaced_with_dots": pii_replaced_with_dots}

    def list_training_log(self, kb_uuid: str) -> List[dict]:
        """Tanítási napló listája (train jog kell)."""
        return self.repo.list_training_log(kb_uuid)

    async def delete_training_point(self, kb_uuid: str, point_id: str) -> None:
        """Egy tanítási bejegyzés törlése a naplóból (nincs Qdrant hívás)."""
        kb = self.repo.get_by_uuid(kb_uuid)
        if not kb or kb.id is None:
            raise ValueError("KB not found")
        deleted = self.repo.delete_training_log_by_point_id(kb.id, point_id)
        if not deleted:
            raise ValueError("Training log entry not found")

    # ------------------------------------------------------------
    #  FILE TRAINING
    # ------------------------------------------------------------
    async def train_from_file(
        self,
        uuid: str,
        file,
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
            current_user_id=current_user_id,
            confirm_pii=confirm_pii,
            pii_review_decision=pii_review_decision,
            pii_decisions=pii_decisions,
        )
