# backend/apps/chat/service/prompt_builder.py
# Feladat: A chat LLM prompt és prompt-context payload összeállítását kezeli. Leválasztja a ChatService-ből a system prompt, history, retrieval context, PII prompt policy és debug payload célú prompt-adat építést, hogy a ChatService orchestration/kompatibilitási réteg felé vékonyodjon. Program-specifikus chat application service boundary.
# Sárközi Mihály - 2026.05.22

from __future__ import annotations

from typing import Any

from apps.chat.service.chat_text_utils import conversation_history_context, retrieval_history_context


class PromptBuilder:
    def __init__(
        self,
        *,
        max_conversation_history_messages: int,
        max_conversation_history_chars: int,
        max_retrieval_history_items: int,
        max_retrieval_history_chars: int,
        multi_kb_packet_score_threshold: float,
        multi_kb_block_score_threshold: float,
        multi_kb_block_relative_floor_ratio: float,
    ) -> None:
        self._max_conversation_history_messages = max(1, int(max_conversation_history_messages))
        self._max_conversation_history_chars = max(1, int(max_conversation_history_chars))
        self._max_retrieval_history_items = max(1, int(max_retrieval_history_items))
        self._max_retrieval_history_chars = max(1, int(max_retrieval_history_chars))
        self._multi_kb_packet_score_threshold = float(multi_kb_packet_score_threshold)
        self._multi_kb_block_score_threshold = float(multi_kb_block_score_threshold)
        self._multi_kb_block_relative_floor_ratio = float(multi_kb_block_relative_floor_ratio)

    def conversation_history_context(self, conversation_history: list[dict[str, str]] | None) -> str:
        return conversation_history_context(
            conversation_history,
            max_messages=self._max_conversation_history_messages,
            max_chars=self._max_conversation_history_chars,
        )

    def retrieval_history_context(self, retrieval_history: list[str] | None) -> str:
        return retrieval_history_context(
            retrieval_history,
            max_items=self._max_retrieval_history_items,
            max_chars=self._max_retrieval_history_chars,
        )

    def build_messages(
        self,
        *,
        question: str,
        context_text: str = "",
        conversation_history: list[dict[str, str]] | None = None,
        retrieval_history: list[str] | None = None,
        pii_prompt_policy: str | None = None,
        brand_voice: str | None = None,
        channel_settings: dict[str, Any] | None = None,
        safety_constraints: str | None = None,
        citation_context: str | None = None,
    ) -> list[dict[str, str]]:
        messages = [
            {
                "role": "system",
                "content": (
                    "Te egy segítőkész asszisztens vagy az AIPLAZA rendszerben. "
                    "Csak a megadott evidence/context alapján válaszolhatsz. "
                    "Ne használj külső tudást. Ne találj ki forrást. "
                    "A beszélgetési előzmény csak a kérdés értelmezésére használható, nem bizonyíték. "
                    "Minden konkrét állításnak a megadott citation/context blokkokhoz kell köthetőnek lennie. "
                    "Ha a context nem tartalmaz választ, mondd: "
                    "\"Nem találtam releváns választ a kiválasztott tudástárban.\" "
                    "Úgy válaszolj, mintha a tudás a saját belső tudásod lenne: természetesen, emberi hangon. "
                    "Ne hivatkozz arra, hogy kontextust, dokumentumot vagy forrást kaptál. "
                    "Válaszolj röviden, legfeljebb 3-4 mondatban."
                ),
            }
        ]
        normalized_brand_voice = str(brand_voice or "").strip()
        if normalized_brand_voice:
            messages.append({"role": "system", "content": f"Brand voice irányelv:\n{normalized_brand_voice}"})
        if channel_settings:
            lines = [f"- {key}: {value}" for key, value in dict(channel_settings).items() if str(value).strip()]
            if lines:
                messages.append({"role": "system", "content": "Channel beállítások:\n" + "\n".join(lines)})
        normalized_safety = str(safety_constraints or "").strip()
        if normalized_safety:
            messages.append({"role": "system", "content": f"Safety szabályok:\n{normalized_safety}"})
        normalized_citation = str(citation_context or "").strip()
        if normalized_citation:
            messages.append({"role": "system", "content": f"Citation context:\n{normalized_citation}"})
        if pii_prompt_policy:
            messages.append({"role": "system", "content": str(pii_prompt_policy or "").strip()})
        history_context = self.conversation_history_context(conversation_history)
        if history_context:
            messages.append(
                {
                    "role": "system",
                    "content": (
                        "Beszélgetési előzmény (kérdés-válasz párok), röviden. "
                        "Ezt kizárólag a kérdés értelmezéséhez használd, ebből önmagában tilos új tényt állítani.\n\n"
                        f"{history_context}"
                    ),
                }
            )
        retrieval_context = self.retrieval_history_context(retrieval_history)
        if retrieval_context:
            messages.append(
                {
                    "role": "system",
                    "content": (
                        "Korábbi kérdésekből megtartott, releváns tudástári találati részletek. "
                        "Ez segéd kontextus, nem elsődleges bizonyíték: tényt csak az aktuális tudástár-contexttel alátámasztva állíts.\n\n"
                        f"{retrieval_context}"
                    ),
                }
            )
        if context_text:
            messages.append(
                {
                    "role": "system",
                    "content": (
                        "A következő tudástár-context alapján válaszolj tömören, "
                        "és csak akkor állíts tényt, ha a context alátámasztja. "
                        "A válasz nyelve mindig egyezzen meg a felhasználó kérdésének nyelvével; "
                        "magyar kérdésre magyarul válaszolj akkor is, ha a context belső címkéi angolul vannak. "
                        "A belső címkéket, például Current facts, Historical vagy Vectoros találatok, ne idézd vissza. "
                        "Ne használj meta-megfogalmazást, például: 'a context alapján', 'a megadott kontextus szerint'. "
                        "Adj közvetlen, természetes választ, mintha a tényeket biztosan tudnád.\n\n"
                        f"{context_text}"
                    ),
                }
            )
        messages.append({"role": "user", "content": question})
        return messages

    def build_prompt_context_payload(
        self,
        *,
        question: str,
        messages: list[dict[str, str]] | None,
        conversation_history: list[dict[str, str]] | None,
        retrieval_history: list[str] | None,
        packet: dict[str, Any],
        context_text: str,
        encoded_question: str | None = None,
        encoded_context_text: str | None = None,
        pii_prompt_policy: str | None = None,
        pii_applied: bool | None = None,
        pii_reason: str | None = None,
        encoded_answer_text: str | None = None,
        raw_question_before_pii: str | None = None,
        raw_context_before_pii: str | None = None,
        raw_conversation_history_before_pii: list[dict[str, str]] | None = None,
        raw_retrieval_history_before_pii: list[str] | None = None,
    ) -> dict[str, Any]:
        qa_context = self.conversation_history_context(conversation_history)
        retrieval_context = self.retrieval_history_context(retrieval_history)
        info_prompt = ""
        if messages:
            for msg in messages:
                if str(msg.get("role") or "").strip() == "system":
                    info_prompt = str(msg.get("content") or "").strip()
                    if info_prompt:
                        break
        hits: list[dict[str, Any]] = []
        for block in (packet.get("context_blocks") or packet.get("matched_semantic_blocks") or [])[:4]:
            if not isinstance(block, dict):
                continue
            hits.append(
                {
                    "block_id": str(block.get("block_id") or block.get("id") or "").strip(),
                    "source_id": str(block.get("source_id") or "").strip(),
                    "subject": str(block.get("subject") or block.get("primary_subject") or "").strip(),
                    "snippet": str(block.get("snippet") or block.get("text") or "").strip(),
                }
            )
        evidence_rows = [
            item
            for item in (packet.get("evidence_summary") or [])
            if isinstance(item, dict)
        ]
        answer_information_sources: list[dict[str, Any]] = []
        seen_answer_source_ids: set[str] = set()
        for row in evidence_rows:
            source_id = str(row.get("source_id") or "").strip()
            if not source_id or source_id in seen_answer_source_ids:
                continue
            seen_answer_source_ids.add(source_id)
            answer_information_sources.append(
                {
                    "source_id": source_id,
                    "claim_id": str(row.get("claim_id") or "").strip(),
                    "sentence_id": str(row.get("sentence_id") or "").strip(),
                    "claim_text": str(row.get("claim_text") or "").strip(),
                    "sentence_text": str(row.get("sentence_text") or "").strip(),
                }
            )
        raw_context_sent_to_llm = "\n\n".join(
            f"[{str(msg.get('role') or '').strip()}]\n{str(msg.get('content') or '').strip()}"
            for msg in (messages or [])
            if isinstance(msg, dict) and str(msg.get("content") or "").strip()
        ).strip()
        matched_chunks_for_debug = [
            chunk
            for chunk in (packet.get("matched_chunks") or [])
            if isinstance(chunk, dict)
        ]
        packet_retrieval_confidence = 0.0
        try:
            packet_retrieval_confidence = float(packet.get("retrieval_confidence") or 0.0)
        except (TypeError, ValueError):
            packet_retrieval_confidence = 0.0
        if packet_retrieval_confidence <= 0 and matched_chunks_for_debug:
            scores: list[float] = []
            for chunk in matched_chunks_for_debug:
                try:
                    score = float(chunk.get("retrieval_confidence") or 0.0)
                except (TypeError, ValueError):
                    score = 0.0
                if score > 0:
                    scores.append(score)
            if scores:
                packet_retrieval_confidence = round(sum(scores) / len(scores), 4)
        index_debug = {
            "retrieval_confidence": packet_retrieval_confidence,
            "timing_ms": packet.get("_chat_timing_ms") or {},
            "query_profile": packet.get("query_profile") or packet.get("query_focus") or {},
            "scoring_summary": packet.get("scoring_summary") or {},
            "filtered_out_reason": packet.get("filtered_out_reason") or [],
            "thresholds": {
                "packet_score_threshold": self._multi_kb_packet_score_threshold,
                "block_score_threshold": self._multi_kb_block_score_threshold,
                "block_relative_floor_ratio": self._multi_kb_block_relative_floor_ratio,
                "dynamic_block_score_threshold": float(packet.get("dynamic_block_score_threshold") or 0.0),
            },
            "selected_blocks": [
                {
                    "kb_uuid": str(block.get("kb_uuid") or packet.get("kb_uuid") or "").strip(),
                    "block_id": str(block.get("block_id") or block.get("id") or "").strip(),
                    "source_id": str(block.get("source_id") or "").strip(),
                    "match_score": float(block.get("match_score") or 0.0),
                    "match_reason": block.get("match_reason") or {},
                }
                for block in (packet.get("context_blocks") or packet.get("matched_semantic_blocks") or [])[:8]
                if isinstance(block, dict)
            ],
            "matched_chunks": [
                {
                    "profile_id": str(chunk.get("profile_id") or "").strip(),
                    "entity_name": str(chunk.get("entity_name") or "").strip(),
                    "retrieval_confidence": float(chunk.get("retrieval_confidence") or 0.0),
                    "matched_claim_ids": list(chunk.get("matched_claim_ids") or []),
                }
                for chunk in matched_chunks_for_debug[:8]
            ],
            "multi_kb_diagnostics": packet.get("multi_kb_diagnostics") or {},
        }
        return {
            "informational_prompt": info_prompt,
            "qa_context": qa_context,
            "retrieval_context": retrieval_context,
            "latest_question": str(question or "").strip(),
            "raw_context_sent_to_llm": raw_context_sent_to_llm,
            "context_components": {
                "alap_context": str(context_text or "").strip(),
                "elozmenyek": qa_context,
                "kerdes": str(question or "").strip(),
                "valaszinformacio": {
                    "answer_mode": str(packet.get("answer_mode") or "no_answer"),
                    "evidence_summary": evidence_rows,
                    "cited_source_ids": list(packet.get("cited_source_ids") or packet.get("source_ids") or []),
                },
            },
            "raw_inputs_before_pii": {
                "question": str(raw_question_before_pii if raw_question_before_pii is not None else question or "").strip(),
                "context_text": str(raw_context_before_pii if raw_context_before_pii is not None else context_text or "").strip(),
                "conversation_history": list(raw_conversation_history_before_pii or []),
                "retrieval_history": list(raw_retrieval_history_before_pii or []),
            },
            "answer_information_sources": answer_information_sources,
            "latest_hits": hits,
            "llm_context_text": str(context_text or "").strip(),
            "encoded_latest_question": str(encoded_question or question or "").strip(),
            "encoded_llm_context_text": str(encoded_context_text or context_text or "").strip(),
            "encoded_answer_text": str(encoded_answer_text or "").strip(),
            "pii_prompt_policy": str(pii_prompt_policy or "").strip(),
            "pii_applied": pii_applied,
            "pii_reason": str(pii_reason or "").strip(),
            "index_debug": index_debug,
            "messages_sent_to_llm": [
                {"role": str(msg.get("role") or ""), "content": str(msg.get("content") or "")}
                for msg in (messages or [])
            ],
        }


__all__ = ["PromptBuilder"]
