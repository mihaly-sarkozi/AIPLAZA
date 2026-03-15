import logging
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from time import perf_counter
from typing import Any, Optional

from openai import AsyncOpenAI
from openai import APIError, APIConnectionError, APITimeoutError, RateLimitError

from config.settings import settings

logger = logging.getLogger(__name__)


class ChatService:
    def __init__(
        self,
        chat_model: Optional[AsyncOpenAI] = None,
        kb_service: Any = None,
        retrieval_service: Any = None,
        query_parser: Any = None,
        context_builder: Any = None,
    ):
        if not settings.OPENAI_API_KEY and chat_model is None:
            raise ValueError("❌ OPENAI_API_KEY nincs beállítva (config / .env).")
        self.client = chat_model or AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.kb_service = kb_service
        self.retrieval_service = retrieval_service
        self.query_parser = query_parser
        self.context_builder = context_builder
        self._recent_query_focus_by_user: dict[int, dict] = {}

    def capture_retrieval_feedback(
        self,
        trace_id: str,
        helpful: bool | None = None,
        context_useful: bool | None = None,
        wrong_entity_resolution: bool = False,
        wrong_time_slice: bool = False,
        note: str | None = None,
    ) -> dict:
        if self.retrieval_service is None or not hasattr(self.retrieval_service, "capture_feedback"):
            return {"status": "skipped", "reason": "feedback_service_not_available"}
        return self.retrieval_service.capture_feedback(
            trace_id=trace_id,
            helpful=helpful,
            context_useful=context_useful,
            wrong_entity_resolution=wrong_entity_resolution,
            wrong_time_slice=wrong_time_slice,
            note=note,
        )

    @staticmethod
    def _utcnow_naive() -> datetime:
        return datetime.now(UTC).replace(tzinfo=None)

    def _is_followup(self, user_id: int | None, query_focus: dict) -> bool:
        if user_id is None:
            return False
        prev = self._recent_query_focus_by_user.get(int(user_id))
        now = self._utcnow_naive()
        self._recent_query_focus_by_user[int(user_id)] = {
            "at": now,
            "entity_candidates": query_focus.get("entity_candidates") or [],
            "time_window": query_focus.get("time_window") or {},
        }
        if not prev:
            return False
        prev_at = prev.get("at")
        if not isinstance(prev_at, datetime):
            return False
        if (now - prev_at).total_seconds() > 300:
            return False
        prev_entities = {str(x).lower() for x in (prev.get("entity_candidates") or [])}
        curr_entities = {str(x).lower() for x in (query_focus.get("entity_candidates") or [])}
        if prev_entities.intersection(curr_entities):
            return True
        prev_tw = prev.get("time_window") or {}
        curr_tw = query_focus.get("time_window") or {}
        return bool(prev_tw.get("from") and curr_tw.get("from") and prev_tw.get("from") == curr_tw.get("from"))

    async def _build_context_packet(
        self,
        question: str,
        user_id: int | None = None,
        user_role: str | None = None,
        kb_uuid: str | None = None,
        debug: bool = False,
    ) -> dict:
        """Retrieval context packet előállítása chathez."""
        if self.kb_service is None:
            return {
                "query_focus": {},
                "top_assertions": [],
                "evidence_sentences": [],
                "source_chunks": [],
                "related_entities": [],
                "scoring_summary": {},
            }
        if kb_uuid and user_id is not None and not self.kb_service.user_can_use(kb_uuid, user_id, user_role):
            raise PermissionError("Nincs jogosultság a megadott tudástár használatához.")
        t_parse = perf_counter()
        parsed = self.query_parser.parse(question) if self.query_parser is not None else {"intent": "summary"}
        parsed["parse_time_ms"] = round((perf_counter() - t_parse) * 1000.0, 2)

        if user_id is not None:
            if self.retrieval_service is not None and hasattr(self.retrieval_service, "build_context_for_chat"):
                packet = await self.retrieval_service.build_context_for_chat(
                    question=question,
                    current_user_id=user_id,
                    current_user_role=user_role,
                    parsed_query=parsed,
                    kb_uuid=kb_uuid,
                    debug=debug,
                )
                packet["query_focus"] = parsed
                packet["parser_audit"] = parsed.get("parser_audit") or {}
                packet.setdefault("scoring_summary", {})
                packet.setdefault("scoring_summary", {}).setdefault("latency_ms", {})
                packet["scoring_summary"]["latency_ms"]["parse"] = float(parsed.get("parse_time_ms") or 0.0)
                packet["is_followup"] = self._is_followup(user_id, parsed)
                return packet
            if hasattr(self.kb_service, "build_context_for_chat"):
                packet = await self.kb_service.build_context_for_chat(
                    question=question,
                    current_user_id=user_id,
                    current_user_role=user_role,
                    parsed_query=parsed,
                    kb_uuid=kb_uuid,
                )
                packet["query_focus"] = parsed
                packet["parser_audit"] = parsed.get("parser_audit") or {}
                packet.setdefault("scoring_summary", {})
                packet.setdefault("scoring_summary", {}).setdefault("latency_ms", {})
                packet["scoring_summary"]["latency_ms"]["parse"] = float(parsed.get("parse_time_ms") or 0.0)
                packet["is_followup"] = self._is_followup(user_id, parsed)
                return packet

        assertions = []
        if user_id is not None:
            assertions = self.kb_service.search_assertions(
                current_user_id=user_id,
                current_user_role=user_role,
                predicates=None,
                entity_ids=None,
                limit=18,
            )
        packet = (
            self.context_builder.build_context_packet(assertions, [], [], [])
            if self.context_builder is not None
            else {"top_assertions": assertions}
        )
        packet["query_focus"] = parsed
        packet["parser_audit"] = parsed.get("parser_audit") or {}
        packet.setdefault("scoring_summary", {})
        packet.setdefault("scoring_summary", {}).setdefault("latency_ms", {})
        packet["scoring_summary"]["latency_ms"]["parse"] = float(parsed.get("parse_time_ms") or 0.0)
        packet["is_followup"] = self._is_followup(user_id, parsed)
        return packet

    async def _safe_context_text(
        self,
        question: str,
        user_id: int | None = None,
        user_role: str | None = None,
        kb_uuid: str | None = None,
        debug: bool = False,
    ) -> str:
        """Hibatűrő context építés: retrieval hiba esetén üres contexttel megy tovább."""
        try:
            packet = await self._build_context_packet(
                question=question,
                user_id=user_id,
                user_role=user_role,
                kb_uuid=kb_uuid,
                debug=debug,
            )
            return self._context_text_from_packet(packet)
        except PermissionError:
            raise
        except Exception as e:
            logger.warning("Knowledge context építés sikertelen, fallback LLM-only mód: %s", e, exc_info=True)
            return ""

    def _context_text_from_packet(self, packet: dict) -> str:
        """Tömör szöveges context építése packetből."""
        top = packet.get("summary_assertions") or packet.get("top_assertions") or []
        assertion_lines = []
        for row in top[:8]:
            text = row.get("text") or row.get("canonical_text") or row.get("payload", {}).get("text") or ""
            if text:
                assertion_lines.append(f"- [A] {text}")
        # Assertion-first guard rail: assertion nélkül nincs context prompt.
        if not assertion_lines:
            return ""
        sentence_lines = packet.get("evidence_sentences") or []
        chunk_lines = packet.get("source_chunks") or []
        related_entities = packet.get("related_entities") or []
        time_slices = packet.get("time_slice_groups") or []
        timeline_sequence = packet.get("timeline_sequence") or []
        conflicts = packet.get("conflict_bundles") or []
        refinements = packet.get("refinement_bundles") or []
        top_lines = list(assertion_lines)
        for row in sentence_lines[:5]:
            text = row.get("text") or row.get("payload", {}).get("text") or ""
            if text:
                top_lines.append(f"- [S] {text}")
        for row in chunk_lines[:3]:
            text = row.get("text") or row.get("payload", {}).get("text") or ""
            if text:
                top_lines.append(f"- [C] {text}")
        query_focus = packet.get("query_focus") or {}
        entity_lines = [
            f"- [E] {x.get('canonical_name') or x.get('entity_id')}"
            for x in related_entities[:5]
        ]
        slice_lines = [
            f"- [T] {str(x.get('time_from') or '')[:10]}..{str(x.get('time_to') or '')[:10]} ({len(x.get('assertion_ids') or [])} állítás)"
            for x in time_slices[:4]
        ]
        timeline_lines = [
            f"- [TL] {str(x.get('time_from') or '')[:10]} {x.get('text') or ''}"
            for x in timeline_sequence[:6]
        ]
        conflict_lines = [
            f"- [CF] {x.get('focus_key')} ({len(x.get('items') or [])} ellentmondó állítás)"
            for x in conflicts[:3]
        ]
        refinement_lines = [
            f"- [RF] {x.get('focus_key')} ({len(x.get('assertion_ids') or [])} finomított állítás)"
            for x in refinements[:3]
        ]
        intent = str(query_focus.get("intent", "summary"))
        base = (
            f"Intent: {intent}\n"
            f"Retrieval mode: {query_focus.get('retrieval_mode', 'assertion_first')}\n"
            "Key assertions:\n"
            + "\n".join(top_lines)
            + ("\nRelated entities:\n" + "\n".join(entity_lines) if entity_lines else "")
            + ("\nTime slices:\n" + "\n".join(slice_lines) if slice_lines else "")
            + ("\nConflicts:\n" + "\n".join(conflict_lines) if conflict_lines else "")
            + ("\nRefinements:\n" + "\n".join(refinement_lines) if refinement_lines else "")
        )
        if intent == "timeline":
            return base + ("\nChronology:\n" + "\n".join(timeline_lines) if timeline_lines else "")
        if intent == "comparison":
            cmp = packet.get("comparison_summary") or {}
            return (
                base
                + "\nComparison focus:\n"
                + f"- left={cmp.get('left_target')} ({cmp.get('left_count', 0)})\n"
                + f"- right={cmp.get('right_target')} ({cmp.get('right_count', 0)})"
            )
        if intent == "relation":
            return base + "\nRelation guidance: koncentrálj a kapcsolati állításokra és bizonyítékra."
        if intent == "attribute":
            return base + "\nAttribute guidance: emeld ki az attribútum és státusz jellegű állításokat."
        return base

    def _build_sources_from_packet(self, packet: dict) -> list[dict]:
        """Forráslista összeállítása a context packetből."""
        rows = []
        for key in ["top_assertions", "evidence_sentences", "source_chunks"]:
            rows.extend(packet.get(key) or [])
        seen: set[tuple[str, str]] = set()
        out: list[dict] = []
        for row in rows:
            kb_uuid = str(row.get("kb_uuid") or "").strip()
            point_id = str(row.get("source_point_id") or "").strip()
            if not kb_uuid or not point_id:
                continue
            item_key = (kb_uuid, point_id)
            if item_key in seen:
                continue
            seen.add(item_key)
            out.append(
                {
                    "kb_uuid": kb_uuid,
                    "point_id": point_id,
                    "title": str(row.get("source_document_title") or ""),
                    "snippet": str(row.get("text") or row.get("canonical_text") or "")[:220],
                }
            )
            if len(out) >= 8:
                break
        return out

    async def chat(
        self,
        question: str,
        user_id: int | None = None,
        user_role: str | None = None,
        kb_uuid: str | None = None,
        debug: bool = False,
    ) -> str:
        """Chat üzenet küldése OpenAI API-nak (egyszeri válasz)."""
        try:
            context_text = await self._safe_context_text(
                question=question,
                user_id=user_id,
                user_role=user_role,
                kb_uuid=kb_uuid,
                debug=debug,
            )
            messages = [{"role": "system", "content": "Te egy segítőkész asszisztens vagy az AIPLAZA rendszerben."}]
            if context_text:
                messages.append(
                    {
                        "role": "system",
                        "content": (
                            "A következő tudástár-context alapján válaszolj tömören, "
                            "és csak akkor állíts tényt, ha a context alátámasztja.\n\n"
                            f"{context_text}"
                        ),
                    }
                )
            messages.append({"role": "user", "content": question})
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
            )
            if not response.choices or not response.choices[0].message.content:
                logger.warning("Üres válasz érkezett az OpenAI API-tól")
                return "⚠️ Nem sikerült választ kapni a modellből."
            answer = response.choices[0].message.content
            if debug and context_text:
                return f"{answer}\n\n[debug-context]\n{context_text}"
            return answer
        except RateLimitError as e:
            logger.error(f"OpenAI rate limit hiba: {e}", exc_info=True)
            return "⚠️ Túl sok kérés. Kérlek, próbáld újra később."
        except APITimeoutError as e:
            logger.error(f"OpenAI timeout hiba: {e}", exc_info=True)
            return "⚠️ A válasz túl sokáig tartott. Kérlek, próbáld újra."
        except APIConnectionError as e:
            logger.error(f"OpenAI kapcsolati hiba: {e}", exc_info=True)
            return "⚠️ Kapcsolati probléma történt. Kérlek, próbáld újra."
        except APIError as e:
            logger.error(f"OpenAI API hiba: {e}", exc_info=True)
            return "⚠️ Nem sikerült választ kapni a modellből."
        except Exception as e:
            logger.error(f"Váratlan hiba a chat szolgáltatásban: {e}", exc_info=True)
            return "⚠️ Nem sikerült választ kapni a modellből."

    async def chat_with_sources(
        self,
        question: str,
        user_id: int | None = None,
        user_role: str | None = None,
        kb_uuid: str | None = None,
        debug: bool = False,
    ) -> dict:
        """Chat válasz forráslistával együtt."""
        packet: dict = {}
        try:
            packet = await self._build_context_packet(
                question=question,
                user_id=user_id,
                user_role=user_role,
                kb_uuid=kb_uuid,
                debug=debug,
            )
            context_text = self._context_text_from_packet(packet)
        except PermissionError:
            raise
        except Exception as e:
            logger.warning("chat_with_sources context hiba, fallback LLM-only: %s", e, exc_info=True)
            context_text = ""
            packet = {}

        messages = [{"role": "system", "content": "Te egy segítőkész asszisztens vagy az AIPLAZA rendszerben."}]
        if context_text:
            messages.append(
                {
                    "role": "system",
                    "content": (
                        "A következő tudástár-context alapján válaszolj tömören, "
                        "és csak akkor állíts tényt, ha a context alátámasztja.\n\n"
                        f"{context_text}"
                    ),
                }
            )
        messages.append({"role": "user", "content": question})
        response = await self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
        )
        answer = (
            response.choices[0].message.content
            if response.choices and response.choices[0].message.content
            else "⚠️ Nem sikerült választ kapni a modellből."
        )
        payload = {
            "answer": answer,
            "sources": self._build_sources_from_packet(packet),
        }
        if packet.get("is_followup") and self.kb_service is not None:
            for row in packet.get("top_assertions") or []:
                aid = str(row.get("id") or "")
                kb_uuid_for_row = str(row.get("kb_uuid") or kb_uuid or "")
                if aid.startswith("assertion-") and aid.split("-", 1)[1].isdigit() and kb_uuid_for_row:
                    try:
                        self.kb_service.reinforce_assertion(
                            kb_uuid=kb_uuid_for_row,
                            assertion_id=int(aid.split("-", 1)[1]),
                            event_type="USER_FOLLOWUP",
                        )
                    except Exception:
                        pass
        if debug:
            payload["debug"] = {
                "query_focus": (packet.get("query_focus") if packet else {}),
                "scoring_summary": (packet.get("scoring_summary") if packet else {}),
            }
        return payload

    async def chat_stream(
        self,
        question: str,
        user_id: int | None = None,
        user_role: str | None = None,
        kb_uuid: str | None = None,
    ) -> AsyncIterator[str]:
        """Streamelt chat válasz: tokenenként yield-eli a tartalmat."""
        try:
            context_text = await self._safe_context_text(
                question=question,
                user_id=user_id,
                user_role=user_role,
                kb_uuid=kb_uuid,
                debug=False,
            )
            messages = [{"role": "system", "content": "Te egy segítőkész asszisztens vagy az AIPLAZA rendszerben."}]
            if context_text:
                messages.append(
                    {
                        "role": "system",
                        "content": (
                            "Használd a tudástár contextet a válaszhoz:\n"
                            f"{context_text}"
                        ),
                    }
                )
            messages.append({"role": "user", "content": question})
            stream = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                stream=True,
            )
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except RateLimitError as e:
            logger.error(f"OpenAI rate limit hiba: {e}", exc_info=True)
            yield "⚠️ Túl sok kérés. Kérlek, próbáld újra később."
        except APITimeoutError as e:
            logger.error(f"OpenAI timeout hiba: {e}", exc_info=True)
            yield "⚠️ A válasz túl sokáig tartott. Kérlek, próbáld újra."
        except APIConnectionError as e:
            logger.error(f"OpenAI kapcsolati hiba: {e}", exc_info=True)
            yield "⚠️ Kapcsolati probléma történt. Kérlek, próbáld újra."
        except APIError as e:
            logger.error(f"OpenAI API hiba: {e}", exc_info=True)
            yield "⚠️ Nem sikerült választ kapni a modellből."
        except Exception as e:
            logger.error(f"Váratlan hiba a chat szolgáltatásban: {e}", exc_info=True)
            yield "⚠️ Nem sikerült választ kapni a modellből."
