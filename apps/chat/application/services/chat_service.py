import logging
import re
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from time import perf_counter
from typing import Any, Optional

from openai import AsyncOpenAI
from openai import APIError, APIConnectionError, APITimeoutError, RateLimitError

from config.settings import settings

logger = logging.getLogger(__name__)


class ChatService:
    _YEAR_RE = re.compile(r"\b(19\d{2}|20\d{2}|21\d{2})\b")
    _DATE_RE = re.compile(r"\b(19\d{2}|20\d{2}|21\d{2})-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])\b")
    _YEAR_MONTH_RE = re.compile(r"\b(19\d{2}|20\d{2}|21\d{2})-(0[1-9]|1[0-2])\b")
    _CAP_SEQ_RE = re.compile(r"\b(?:[A-ZÁÉÍÓÖŐÚÜŰ][\wÁÉÍÓÖŐÚÜŰáéíóöőúüű-]*)(?:\s+[A-ZÁÉÍÓÖŐÚÜŰ][\wÁÉÍÓÖŐÚÜŰáéíóöőúüű-]*)*\b")
    _WORD_RE = re.compile(r"[A-Za-zÁÉÍÓÖŐÚÜŰáéíóöőúüű0-9_-]{3,}")
    _MONTHS = {
        "január": 1,
        "február": 2,
        "március": 3,
        "április": 4,
        "május": 5,
        "június": 6,
        "július": 7,
        "augusztus": 8,
        "szeptember": 9,
        "október": 10,
        "november": 11,
        "december": 12,
    }
    _ENTITY_STOPWORDS = {
        "Ki", "Kik", "Mi", "Mit", "Mikor", "Hol", "Hogyan", "Mennyi", "Melyik",
        "Mutasd", "Mondd", "Keresd", "Van", "Volt", "Lesz", "A", "Az", "És", "Vagy",
    }
    _PLACE_SUFFIXES = (
        "ban", "ben", "on", "en", "ön", "ba", "be", "ra", "re", "nál", "nél", "ból", "ből", "hoz", "hez", "höz",
    )
    _QUESTION_STOPWORDS = {
        "ki", "kik", "mi", "mit", "mikor", "hol", "hogyan", "milyen", "mennyi", "melyik",
        "van", "volt", "lesz", "egy", "az", "a", "és", "vagy", "meg", "hogy", "akkor",
    }

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

    @staticmethod
    def _dedupe_keep_order(values: list[str]) -> list[str]:
        out: list[str] = []
        seen: set[str] = set()
        for value in values:
            item = " ".join(str(value or "").strip().split())
            if not item:
                continue
            key = item.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(item)
        return out

    @staticmethod
    def _sanitize_debug_text(value: Any) -> str:
        text = str(value or "")
        if not text:
            return ""
        text = re.sub(r"(?i)\b[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}\b", "[redacted_email]", text)
        text = re.sub(r"\b(?:\+?\d[\d\s().-]{6,}\d)\b", "[redacted_phone]", text)
        text = re.sub(r"\b\d{6,}\b", "[redacted_number]", text)
        return text[:400] + ("..." if len(text) > 400 else "")

    @classmethod
    def _sanitize_debug_value(cls, value: Any) -> Any:
        if isinstance(value, dict):
            return {str(k): cls._sanitize_debug_value(v) for k, v in value.items()}
        if isinstance(value, list):
            return [cls._sanitize_debug_value(v) for v in value]
        if isinstance(value, tuple):
            return [cls._sanitize_debug_value(v) for v in value]
        if isinstance(value, str):
            return cls._sanitize_debug_text(value)
        return value

    @classmethod
    def _normalize_place_surface(cls, value: str) -> str:
        raw = " ".join(str(value or "").strip().split())
        if not raw:
            return ""
        lower = raw.lower()
        for suffix in sorted(cls._PLACE_SUFFIXES, key=len, reverse=True):
            if lower.endswith(suffix) and len(raw) > len(suffix) + 2:
                return raw[: len(raw) - len(suffix)]
        return raw

    @classmethod
    def _extract_entity_candidates(cls, question: str) -> list[str]:
        out: list[str] = []
        for match in cls._CAP_SEQ_RE.findall(question or ""):
            value = " ".join(str(match).split())
            if not value or value in cls._ENTITY_STOPWORDS:
                continue
            out.append(value)
        return cls._dedupe_keep_order(out)

    @classmethod
    def _extract_place_candidates(cls, question: str) -> list[str]:
        words = re.findall(r"\b[\wÁÉÍÓÖŐÚÜŰáéíóöőúüű-]+\b", question or "")
        out: list[str] = []
        for word in words:
            normalized = cls._normalize_place_surface(word)
            if normalized != word and normalized[:1].isupper():
                out.append(normalized)
        for match in cls._CAP_SEQ_RE.findall(question or ""):
            low = f" {(question or '').lower()} "
            value = " ".join(str(match).split())
            if not value:
                continue
            probe = value.lower()
            if any(
                token in low
                for token in (
                    f" {probe.lower()} ban ", f" {probe.lower()} ben ", f" {probe.lower()} on ",
                    f" {probe.lower()} en ", f" {probe.lower()} ön ", f" {probe.lower()} területén ",
                    f" {probe.lower()} városban ", f" {probe.lower()} megyében ",
                )
            ):
                out.append(value)
        return cls._dedupe_keep_order(out)

    @classmethod
    def _extract_time_hints(cls, question: str) -> tuple[list[str], dict[str, datetime | None]]:
        text = str(question or "")
        low = text.lower()
        now = cls._utcnow_naive()
        candidates: list[str] = []
        window = {"from": None, "to": None}
        for year, month, day in cls._DATE_RE.findall(text):
            candidates.append(f"{year}-{month}-{day}")
            dt = datetime(int(year), int(month), int(day), 0, 0, 0)
            window["from"] = dt
            window["to"] = dt.replace(hour=23, minute=59, second=59)
            return cls._dedupe_keep_order(candidates), window
        for year, month in cls._YEAR_MONTH_RE.findall(text):
            candidates.append(f"{year}-{month}")
            start = datetime(int(year), int(month), 1, 0, 0, 0)
            if int(month) == 12:
                end = datetime(int(year), 12, 31, 23, 59, 59)
            else:
                end = datetime(int(year), int(month) + 1, 1, 0, 0, 0) - timedelta(seconds=1)
            window["from"] = start
            window["to"] = end
            return cls._dedupe_keep_order(candidates), window
        years = cls._YEAR_RE.findall(text)
        if years:
            year = int(years[0])
            candidates.extend(years)
            window["from"] = datetime(year, 1, 1, 0, 0, 0)
            window["to"] = datetime(year, 12, 31, 23, 59, 59)
            return cls._dedupe_keep_order(candidates), window
        for month_name, month_num in cls._MONTHS.items():
            if month_name in low:
                candidates.append(month_name)
                year = now.year
                year_match = cls._YEAR_RE.search(text)
                if year_match:
                    year = int(year_match.group(1))
                start = datetime(year, month_num, 1, 0, 0, 0)
                if month_num == 12:
                    end = datetime(year, 12, 31, 23, 59, 59)
                else:
                    end = datetime(year, month_num + 1, 1, 0, 0, 0) - timedelta(seconds=1)
                window["from"] = start
                window["to"] = end
                return cls._dedupe_keep_order(candidates), window
        if "tavaly" in low:
            year = now.year - 1
            candidates.append("tavaly")
            window["from"] = datetime(year, 1, 1, 0, 0, 0)
            window["to"] = datetime(year, 12, 31, 23, 59, 59)
        elif "idén" in low:
            candidates.append("idén")
            window["from"] = datetime(now.year, 1, 1, 0, 0, 0)
            window["to"] = datetime(now.year, 12, 31, 23, 59, 59)
        elif "most" in low or "jelenleg" in low:
            candidates.append("most")
            window["from"] = datetime(now.year, now.month, 1, 0, 0, 0)
            if now.month == 12:
                window["to"] = datetime(now.year, 12, 31, 23, 59, 59)
            else:
                window["to"] = datetime(now.year, now.month + 1, 1, 0, 0, 0) - timedelta(seconds=1)
        return cls._dedupe_keep_order(candidates), window

    @classmethod
    def _derive_intent(cls, question: str, parsed: dict) -> str:
        low = str(question or "").lower()
        if any(x in low for x in ("időrend", "timeline", "mikor", "meddig", "mettől", "előtte", "utána")):
            return "timeline"
        if any(x in low for x in ("kapcsolat", "viszony", "kapcsolódik", "kapcsolódnak", "köze van")):
            return "relation"
        if any(x in low for x in ("milyen", "mennyi", "mekkora", "státusz", "állapot", "attribútum")):
            return "attribute"
        if any(x in low for x in ("mit csinál", "mit csinált", "mi történt", "ki dolgozik", "ki vezet")):
            return "activity"
        entities = parsed.get("entity_candidates") or []
        predicates = parsed.get("predicate_candidates") or []
        if predicates and entities:
            return "activity"
        return str(parsed.get("intent") or "summary")

    @classmethod
    def _build_hint_terms(cls, question: str, parsed: dict) -> list[str]:
        low = str(question or "").lower()
        tokens = [token for token in cls._WORD_RE.findall(low) if token not in cls._QUESTION_STOPWORDS]
        blocked = {
            str(x).lower()
            for key in ("entity_candidates", "place_candidates", "time_candidates")
            for x in (parsed.get(key) or [])
        }
        out = [
            token for token in tokens
            if token not in blocked and len(token) >= 4
        ]
        return cls._dedupe_keep_order(out[:8])

    @classmethod
    def _enrich_parsed_query(cls, question: str, parsed: dict) -> dict:
        parsed = dict(parsed or {})
        parsed.setdefault("raw_query", question)
        parsed["entity_candidates"] = cls._dedupe_keep_order(
            list(parsed.get("entity_candidates") or []) + cls._extract_entity_candidates(question)
        )
        parsed["place_candidates"] = cls._dedupe_keep_order(
            list(parsed.get("place_candidates") or []) + cls._extract_place_candidates(question)
        )
        time_candidates, time_window = cls._extract_time_hints(question)
        parsed["time_candidates"] = cls._dedupe_keep_order(
            list(parsed.get("time_candidates") or []) + time_candidates
        )
        if parsed.get("query_valid_time_from") is None and time_window.get("from") is not None:
            parsed["query_valid_time_from"] = time_window["from"]
        if parsed.get("query_valid_time_to") is None and time_window.get("to") is not None:
            parsed["query_valid_time_to"] = time_window["to"]
        parsed["valid_time_window"] = parsed.get("valid_time_window") or {
            "from": parsed.get("query_valid_time_from").isoformat() if parsed.get("query_valid_time_from") else None,
            "to": parsed.get("query_valid_time_to").isoformat() if parsed.get("query_valid_time_to") else None,
        }
        parsed["time_window"] = parsed.get("time_window") or parsed["valid_time_window"]
        parsed["intent"] = cls._derive_intent(question, parsed)
        hint_terms = cls._build_hint_terms(question, parsed)
        parsed["lexical_focus_terms"] = cls._dedupe_keep_order(
            list(parsed.get("lexical_focus_terms") or [])
            + list(parsed.get("predicate_candidates") or [])
            + list(parsed.get("attribute_candidates") or [])
            + list(parsed.get("relation_candidates") or [])
            + hint_terms
        )
        parsed["entity_heavy"] = bool(parsed.get("entity_heavy")) or len(parsed["entity_candidates"]) >= 2
        parsed["predicate_heavy"] = bool(parsed.get("predicate_heavy")) or bool(parsed.get("predicate_candidates"))
        if not parsed.get("retrieval_mode") or parsed.get("retrieval_mode") == "assertion_first":
            intent = str(parsed.get("intent") or "summary")
            if intent == "timeline":
                parsed["retrieval_mode"] = "timeline_first"
            elif intent in {"relation", "attribute"} or parsed.get("entity_heavy"):
                parsed["retrieval_mode"] = "entity_first"
            else:
                parsed["retrieval_mode"] = "assertion_first"
        representation_parts = [
            str(parsed.get("raw_query") or question),
            " ".join(parsed.get("entity_candidates") or []),
            " ".join(parsed.get("place_candidates") or []),
            " ".join(parsed.get("time_candidates") or []),
            " ".join(parsed.get("predicate_candidates") or []),
            " ".join(parsed.get("relation_candidates") or []),
            " ".join(parsed.get("attribute_candidates") or []),
            " ".join(parsed.get("lexical_focus_terms") or []),
        ]
        normalized_representation = " ".join(part.strip() for part in representation_parts if str(part).strip())
        parsed["normalized_query_text"] = parsed.get("normalized_query_text") or normalized_representation
        parsed["lexical_query_text"] = parsed.get("lexical_query_text") or normalized_representation
        parsed["query_embedding_text"] = parsed.get("query_embedding_text") or normalized_representation
        parser_audit = dict(parsed.get("parser_audit") or {})
        parser_audit["chat_enrichment"] = {
            "entity_candidates": parsed.get("entity_candidates") or [],
            "time_candidates": parsed.get("time_candidates") or [],
            "place_candidates": parsed.get("place_candidates") or [],
            "intent": parsed.get("intent"),
            "retrieval_mode": parsed.get("retrieval_mode"),
            "lexical_focus_terms": parsed.get("lexical_focus_terms") or [],
            "normalized_query_text": parsed.get("normalized_query_text"),
        }
        parsed["parser_audit"] = parser_audit
        return parsed

    def _is_followup(self, user_id: int | None, query_focus: dict) -> bool:
        if user_id is None:
            return False
        prev = self._recent_query_focus_by_user.get(int(user_id))
        now = self._utcnow_naive()
        self._recent_query_focus_by_user[int(user_id)] = {
            "at": now,
            "entity_candidates": query_focus.get("entity_candidates") or [],
            "valid_time_window": query_focus.get("valid_time_window") or query_focus.get("time_window") or {},
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
        prev_tw = prev.get("valid_time_window") or prev.get("time_window") or {}
        curr_tw = query_focus.get("valid_time_window") or query_focus.get("time_window") or {}
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
        parsed = self._enrich_parsed_query(question, parsed)
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
        primary = packet.get("primary_assertions") or packet.get("seed_assertions") or packet.get("summary_assertions") or packet.get("top_assertions") or []
        supporting = packet.get("supporting_assertions") or packet.get("expanded_assertions") or []
        primary_lines = []
        for row in primary[:6]:
            text = row.get("text") or row.get("canonical_text") or row.get("payload", {}).get("text") or ""
            if text:
                primary_lines.append(f"- [A] {text}")
        # Assertion-first guard rail: assertion nélkül nincs context prompt.
        if not primary_lines:
            return ""
        sentence_lines = packet.get("evidence_sentences") or []
        chunk_lines = packet.get("source_chunks") or []
        related_entities = packet.get("related_entities") or []
        related_places = packet.get("related_places") or []
        time_slices = packet.get("time_slice_groups") or []
        timeline_sequence = packet.get("timeline_sequence") or []
        conflicts = packet.get("conflict_bundles") or []
        refinements = packet.get("refinement_bundles") or []
        supporting_lines = []
        primary_ids = {
            str(row.get("id"))
            for row in primary[:6]
            if row.get("id") is not None
        }
        for row in supporting[:6]:
            if str(row.get("id")) in primary_ids:
                continue
            text = row.get("text") or row.get("canonical_text") or row.get("payload", {}).get("text") or ""
            if text:
                supporting_lines.append(f"- [SA] {text}")
        evidence_lines = []
        for row in sentence_lines[:6]:
            text = row.get("text") or row.get("payload", {}).get("text") or ""
            if text:
                prefix = "[S]" if str(row.get("context_role") or "").startswith("primary") else "[SE]"
                evidence_lines.append(f"- {prefix} {text}")
        chunk_text_lines = []
        for row in chunk_lines[:3]:
            text = row.get("text") or row.get("payload", {}).get("text") or ""
            if text:
                prefix = "[C]" if str(row.get("context_role") or "") == "primary_chunk" else "[CF]"
                chunk_text_lines.append(f"- {prefix} {text}")
        query_focus = packet.get("query_focus") or {}
        entity_lines = [
            f"- [E] {x.get('canonical_name') or x.get('entity_id')}"
            for x in related_entities[:5]
        ]
        place_lines = [
            f"- [P] {x.get('place_key')} ({len(x.get('assertion_ids') or [])} állítás)"
            for x in related_places[:5]
            if x.get("place_key")
        ]
        slice_lines = [
            f"- [T] {str(x.get('valid_time_from') or x.get('time_from') or '')[:10]}..{str(x.get('valid_time_to') or x.get('time_to') or '')[:10]} ({len(x.get('assertion_ids') or [])} állítás)"
            for x in time_slices[:4]
        ]
        timeline_lines = [
            f"- [TL] {str(x.get('valid_time_from') or x.get('time_from') or '')[:10]} {x.get('text') or ''}"
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
            "Primary assertions:\n"
            + "\n".join(primary_lines)
            + ("\nSupporting assertions:\n" + "\n".join(supporting_lines) if supporting_lines else "")
            + ("\nEvidence sentences:\n" + "\n".join(evidence_lines) if evidence_lines else "")
            + ("\nContext chunks:\n" + "\n".join(chunk_text_lines) if chunk_text_lines else "")
            + ("\nRelated entities:\n" + "\n".join(entity_lines) if entity_lines else "")
            + ("\nPlaces:\n" + "\n".join(place_lines) if place_lines else "")
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
                    "title": self._sanitize_debug_text(row.get("source_document_title") or ""),
                    "snippet": self._sanitize_debug_text(str(row.get("text") or row.get("canonical_text") or "")[:220]),
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
                return f"{answer}\n\n[debug-context]\n{self._sanitize_debug_text(context_text)}"
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
                "query_focus": self._sanitize_debug_value(packet.get("query_focus") if packet else {}),
                "scoring_summary": self._sanitize_debug_value(packet.get("scoring_summary") if packet else {}),
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
