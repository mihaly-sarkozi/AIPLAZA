# backend/apps/chat/service/pii_chat_guard_service.py
# Owns KB-scoped chat PII policy, prompt guarding, audit, metrics and answer restore.

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from time import perf_counter
from typing import Any, Callable

from apps.chat.errors import ChatProviderUnavailable
from core.kernel.interface.observability import increment_metric, log_structured_event, observe_metric
from shared.text.language_lexicon import get_lexicon_terms
from shared.utils import sanitize_log_data

logger = logging.getLogger(__name__)

_AUDIT_ACTION_KNOWLEDGE_PII_DEPERSONALIZED = "knowledge_pii_depersonalized"
_PII_POLICY_REFUSAL_TEXT = (
    "Az adott név adatvédelmi okból tokenizálva van; a teljes választ a felület automatikusan visszacseréli."
)
_PII_ENCODE_UNAVAILABLE_DETAIL = (
    "PII deperszonalizációs szolgáltatás átmenetileg nem érhető el, próbáld újra később."
)
_QUESTION_NAME_SUFFIXES = get_lexicon_terms("hu", "name_suffixes", include_fallback=False)


class PiiDepersonalizationUnavailableError(ChatProviderUnavailable):
    """Raised when KB-level PII depersonalization cannot be guaranteed."""

    code = "PII_DEPERSONALIZATION_UNAVAILABLE"
    safe_message = _PII_ENCODE_UNAVAILABLE_DETAIL


@dataclass
class PiiChatContext:
    enabled: bool = False
    sensitivity: str = "medium"
    corpus_uuid: str = ""
    prompt_policy: str = ""
    encoded_question: str = ""
    encoded_context_text: str = ""
    encoded_conversation_history: list[dict[str, str]] | None = None
    encoded_retrieval_history: list[str] | None = None
    applied: bool | None = None
    reason: str = ""
    allowed_rehydrate_tokens: set[str] = field(default_factory=set)
    raw_question_before_pii: str = ""
    raw_context_before_pii: str = ""
    raw_conversation_history_before_pii: list[dict[str, str]] = field(default_factory=list)
    raw_retrieval_history_before_pii: list[str] = field(default_factory=list)
    encode_duration_ms: float = 0.0


@dataclass
class PiiRestoredAnswer:
    text: str
    restored_spans: list[dict[str, Any]]


class PiiChatGuardService:
    def __init__(
        self,
        *,
        pii_depersonalization_service: Callable[[], Any | None] | Any | None,
        audit_service: Callable[[], Any | None] | Any | None,
        insufficient_context_answer: Callable[[], str],
    ) -> None:
        self._pii_depersonalization_service = pii_depersonalization_service
        self._audit_service = audit_service
        self._insufficient_context_answer = insufficient_context_answer

    def _pii_service(self) -> Any | None:
        if callable(self._pii_depersonalization_service):
            return self._pii_depersonalization_service()
        return self._pii_depersonalization_service

    def _audit_logger(self) -> Any | None:
        if callable(self._audit_service):
            return self._audit_service()
        return self._audit_service

    @staticmethod
    def kb_pii_settings(*, packet: dict[str, Any], kb_uuid: str | None) -> tuple[bool, str, str]:
        effective_kb_uuid = str(packet.get("kb_uuid") or packet.get("corpus_uuid") or kb_uuid or "").strip()
        enabled = bool(packet.get("pii_depersonalization_enabled", True))
        sensitivity = str(packet.get("personal_data_sensitivity") or "medium").strip() or "medium"
        return enabled, sensitivity, effective_kb_uuid

    @staticmethod
    def prompt_policy() -> str:
        return (
            "PII deperszonalizáció aktív. A contextben és kérdésben [type_index] formátumú tokenek szerepelnek. "
            "A tokenek valós személyes adatok helyettesítői, stabil azonosítóként kell kezelni őket.\n"
            "Gyakori token-típusok (a pontos címke a normalizált pipeline nevet követi):\n"
            "- [szemely_*] = természetes személy neve\n"
            "- [cim_*] = postacím\n"
            "- [azonosito_*], [szemelyi_azonosito_*], [ugyfel_azonosito_*], [utlevel_azonosito_*] = azonosító típusok\n"
            "- [name_*] / [person_*] = természetes személy neve\n"
            "- [email_*] = e-mail cím\n"
            "- [phone_*] = telefonszám\n"
            "- [iban_*] = bankszámla / IBAN\n"
            "- [customer_id_*] = ügyfélazonosító\n"
            "- [date_*] = dátum\n"
            "- [address_*] = postacím\n"
            "- [engine_number_*] / [motorszam_*] = motorszám\n"
            "- [chassis_number_*] / [alvazszam_*] / [vin_*] = alvázszám / VIN\n"
            "- [nie_*] = spanyol NIE azonosító\n"
            "- [vat_*] / [adoszam_*] / [iva_*] = VAT / adószám / IVA azonosító\n"
            "- [passport_*], [personal_id_*], [tax_id_*] = okmány/személyes azonosító\n"
            "Nemzetközi variánsok: hu/en/es címkék is előfordulhatnak ugyanarra az entitásra.\n"
            "Szabályok:\n"
            "1) Soha ne találj ki, egészíts ki vagy fejts vissza személyes adatot tokenből.\n"
            "2) Soha ne módosítsd a token formátumát, és ugyanarra az entitásra mindig ugyanazt a tokent használd.\n"
            "3) Soha ne próbáld meg kitalálni vagy magyarázni, hogy egy token mögött ki a valós személy.\n"
            "4) Ha a felhasználó token mögötti valós nevet kér, udvariasan jelezd, hogy ezt nem adhatod ki, "
            "és maradj a forrásban szereplő, tokenizált tényeknél.\n"
            "5) Bármilyen ismeretlen [*_N] token esetén is kezeld PII-helyettesítőként."
        )

    def normalize_policy_refusal(self, text: str) -> str:
        value = str(text or "").strip()
        if not value:
            return value
        if _PII_POLICY_REFUSAL_TEXT.lower() in value.lower():
            return self._insufficient_context_answer()
        return value

    @staticmethod
    def encode_question_using_context_mappings(
        *,
        question: str,
        context_mappings: list[dict[str, Any]] | None,
        fold_text: Callable[[str | None], str],
    ) -> str:
        text = str(question or "")
        if not text:
            return text
        mappings = [item for item in (context_mappings or []) if isinstance(item, dict)]
        if not mappings:
            return text
        encoded = text
        for item in mappings:
            token = str(item.get("token") or "").strip()
            preview = str(item.get("original_preview") or "").strip()
            if not token or not preview:
                continue
            folded_preview = fold_text(preview)
            if not folded_preview or len(folded_preview) < 3:
                continue
            escaped = re.escape(preview)
            direct_pattern = re.compile(rf"(?iu)\b{escaped}\b")
            if direct_pattern.search(encoded):
                encoded = direct_pattern.sub(token, encoded)
                continue
            suffix_pattern = re.compile(
                rf"(?iu)\b{escaped}(?:{'|'.join(map(re.escape, _QUESTION_NAME_SUFFIXES))})\b"
            )
            encoded = suffix_pattern.sub(token, encoded)
        return encoded

    def audit_encode(
        self,
        *,
        user_id: int | None,
        corpus_uuid: str | None,
        outcome: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        audit_service = self._audit_logger()
        if audit_service is None or not hasattr(audit_service, "log"):
            return
        try:
            sanitized_details = sanitize_log_data(details)
            if isinstance(details, dict) and isinstance(sanitized_details, dict):
                for safe_key in ("pii_items_created", "context_length_chars", "encoded_length_chars"):
                    value = details.get(safe_key)
                    if isinstance(value, (int, float)):
                        sanitized_details[safe_key] = value
            audit_service.log(
                _AUDIT_ACTION_KNOWLEDGE_PII_DEPERSONALIZED,
                user_id=user_id if isinstance(user_id, int) else None,
                target_type="corpus",
                target_id=str(corpus_uuid or "").strip() or None,
                outcome=str(outcome or "unknown"),
                details=sanitized_details,
            )
        except (RuntimeError, ValueError, TypeError) as exc:
            logger.warning("PII encode audit log sikertelen; audit-only failure.", exc_info=True, extra={"error_type": type(exc).__name__})

    @staticmethod
    def emit_encode_metrics(
        *,
        sensitivity: str,
        outcome: str,
        duration_ms: float,
        token_count: int,
    ) -> None:
        metric_increment = increment_metric
        metric_observe = observe_metric
        try:
            from apps.chat.service import chat_service as chat_service_module

            metric_increment = getattr(chat_service_module, "increment_metric", metric_increment)
            metric_observe = getattr(chat_service_module, "observe_metric", metric_observe)
        except (ImportError, AttributeError):
            pass
        tags = {
            "sensitivity": str(sensitivity or "medium"),
            "outcome": str(outcome or "unknown"),
        }
        metric_increment("knowledge.pii.depersonalize.runs", 1.0, tags=tags)
        metric_observe("knowledge.pii.depersonalize.duration_ms", float(max(0.0, duration_ms)), unit="ms", tags=tags)
        metric_observe("knowledge.pii.depersonalize.tokens_per_request", float(max(0, token_count)), unit="count", tags=tags)

    def raise_encode_unavailable(
        self,
        *,
        kb_uuid: str | None,
        corpus_uuid: str | None,
        user_id: int | None,
        source: str,
        sensitivity: str = "medium",
        duration_ms: float = 0.0,
    ) -> None:
        increment_metric("knowledge.pii.encode.failed", 1.0)
        self.emit_encode_metrics(
            sensitivity=sensitivity,
            outcome="failure",
            duration_ms=duration_ms,
            token_count=0,
        )
        self.audit_encode(
            user_id=user_id,
            corpus_uuid=corpus_uuid,
            outcome="failure",
            details={
                "source": source,
                "reason": "encode_exception",
                "kb_uuid": str(kb_uuid or "").strip() or None,
                "corpus_uuid": str(corpus_uuid or "").strip() or None,
                "sensitivity": str(sensitivity or "medium"),
            },
        )
        log_structured_event(
            "apps.chat.service.pii_chat_guard_service",
            "KNOWLEDGE_PII_ENCODE_FAILED",
            level=logging.ERROR,
            reason="encode_exception",
            source=source,
            kb_uuid=str(kb_uuid or "").strip() or None,
            corpus_uuid=str(corpus_uuid or "").strip() or None,
            user_id=int(user_id) if isinstance(user_id, int) else None,
        )
        raise PiiDepersonalizationUnavailableError(_PII_ENCODE_UNAVAILABLE_DETAIL)

    def prepare_question(
        self,
        *,
        packet: dict[str, Any],
        kb_uuid: str | None,
        question: str,
        context_text: str,
        conversation_history: list[dict[str, str]] | None = None,
        retrieval_history: list[str] | None = None,
        user_id: int | None = None,
        source: str,
        include_history: bool = True,
        fold_text: Callable[[str | None], str],
    ) -> PiiChatContext:
        enabled, sensitivity, corpus_uuid = self.kb_pii_settings(packet=packet, kb_uuid=kb_uuid)
        context = PiiChatContext(
            enabled=enabled,
            sensitivity=sensitivity,
            corpus_uuid=corpus_uuid,
            encoded_question=question,
            encoded_context_text=context_text,
            encoded_conversation_history=conversation_history,
            encoded_retrieval_history=retrieval_history,
            raw_question_before_pii=str(question or ""),
            raw_context_before_pii=str(context_text or ""),
            raw_conversation_history_before_pii=list(conversation_history or []),
            raw_retrieval_history_before_pii=list(retrieval_history or []),
        )
        pii_service = self._pii_service()
        if enabled and pii_service is not None and corpus_uuid:
            context.prompt_policy = self.prompt_policy()
            started_at = perf_counter()
            try:
                encoded_question_obj = pii_service.encode_text(
                    corpus_uuid=corpus_uuid,
                    text=question,
                    enabled=True,
                    sensitivity=sensitivity,
                )
                encoded_context_obj = pii_service.encode_text(
                    corpus_uuid=corpus_uuid,
                    text=context_text,
                    enabled=True,
                    sensitivity=sensitivity,
                )
                context.encoded_question = encoded_question_obj.text
                context.encoded_context_text = encoded_context_obj.text
                if (
                    str(context.encoded_question or "").strip() == str(question or "").strip()
                    and (encoded_context_obj.mappings or [])
                ):
                    context.encoded_question = self.encode_question_using_context_mappings(
                        question=question,
                        context_mappings=encoded_context_obj.mappings,
                        fold_text=fold_text,
                    )
                history_mappings: list[dict[str, Any]] = []
                if include_history:
                    context.encoded_conversation_history = []
                    for item in (conversation_history or []):
                        if not isinstance(item, dict):
                            continue
                        role = str(item.get("role") or "").strip()
                        content = str(item.get("content") or "").strip()
                        if not role or not content:
                            continue
                        encoded_item = pii_service.encode_text(
                            corpus_uuid=corpus_uuid,
                            text=content,
                            enabled=True,
                            sensitivity=sensitivity,
                        )
                        history_mappings.extend(encoded_item.mappings or [])
                        context.encoded_conversation_history.append({"role": role, "content": encoded_item.text})
                    context.encoded_retrieval_history = []
                    for raw_item in (retrieval_history or []):
                        raw_text = str(raw_item or "").strip()
                        if not raw_text:
                            continue
                        encoded_item = pii_service.encode_text(
                            corpus_uuid=corpus_uuid,
                            text=raw_text,
                            enabled=True,
                            sensitivity=sensitivity,
                        )
                        history_mappings.extend(encoded_item.mappings or [])
                        context.encoded_retrieval_history.append(encoded_item.text)
                context.applied = True
                context.reason = "PII deperszonalizáció sikeres."
                context.encode_duration_ms = round((perf_counter() - started_at) * 1000.0, 2)
                mappings = [
                    *(encoded_question_obj.mappings or []),
                    *(encoded_context_obj.mappings or []),
                    *history_mappings,
                ]
                context.allowed_rehydrate_tokens = {
                    str(item.get("token") or "").strip()
                    for item in mappings
                    if isinstance(item, dict) and str(item.get("token") or "").strip()
                }
                token_count = len(mappings)
                entity_types = sorted(
                    {
                        str(item.get("entity_type") or "").strip()
                        for item in mappings
                        if isinstance(item, dict) and str(item.get("entity_type") or "").strip()
                    }
                )
                self.emit_encode_metrics(
                    sensitivity=sensitivity,
                    outcome="success",
                    duration_ms=context.encode_duration_ms,
                    token_count=token_count,
                )
                self.audit_encode(
                    user_id=user_id,
                    corpus_uuid=corpus_uuid,
                    outcome="success",
                    details={
                        "source": source,
                        "pii_items_created": token_count,
                        "entity_types": entity_types,
                        "context_length_chars": len(str(context_text or "")),
                        "encoded_length_chars": len(str(context.encoded_context_text or "")),
                        "sensitivity": sensitivity,
                    },
                )
            except (RuntimeError, ValueError, TypeError, AttributeError):
                duration_ms = round((perf_counter() - started_at) * 1000.0, 2)
                logger.error("PII depersonalization encode failed; fail-closed response.", exc_info=True)
                self.raise_encode_unavailable(
                    kb_uuid=kb_uuid,
                    corpus_uuid=corpus_uuid,
                    user_id=user_id,
                    source=source,
                    sensitivity=sensitivity,
                    duration_ms=duration_ms,
                )
        else:
            if not enabled:
                context.applied = False
                context.reason = "A kiválasztott tudástárban a PII deperszonalizáció ki van kapcsolva."
            elif not corpus_uuid:
                context.applied = False
                context.reason = "Összes tudástár módban nincs egyedi KB-azonosító, ezért nem futott PII deperszonalizáció."
            elif pii_service is None:
                context.applied = False
                context.reason = "PII deperszonalizációs szolgáltatás nem elérhető."
        return context

    def restore_answer(self, answer: str, context: PiiChatContext) -> PiiRestoredAnswer:
        text = str(answer or "")
        restored_spans: list[dict[str, Any]] = []
        pii_service = self._pii_service()
        if context.enabled and pii_service is not None and context.corpus_uuid:
            restored = pii_service.rehydrate_text(
                corpus_uuid=context.corpus_uuid,
                text=text,
                enabled=True,
                allowed_tokens=context.allowed_rehydrate_tokens,
            )
            text = restored.text
            restored_spans = restored.restored_spans
        return PiiRestoredAnswer(text=self.normalize_policy_refusal(text), restored_spans=restored_spans)


__all__ = ["PiiChatContext", "PiiChatGuardService", "PiiDepersonalizationUnavailableError", "PiiRestoredAnswer"]
