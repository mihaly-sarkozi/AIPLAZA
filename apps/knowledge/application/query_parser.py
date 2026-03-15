from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta

from apps.knowledge.ports.query_parser_port import QueryParserPort


class QueryParser(QueryParserPort):
    """Kérdés parser MVP entitás/idő/hely/intent kinyeréshez."""

    _CAP_WORD = re.compile(r"\b[A-ZÁÉÍÓÖŐÚÜŰ][a-záéíóöőúüűA-ZÁÉÍÓÖŐÚÜŰ-]+\b")
    _YEAR = re.compile(r"\b(19\d{2}|20\d{2}|21\d{2}|22\d{2}|23\d{2}|24\d{2}|25\d{2}|26\d{2}|27\d{2}|28\d{2}|29\d{2})\b")
    _PLACE_HINT = re.compile(
        r"\b(?:in|at|on|from|to|ban|ben|on|en|ön|város|city|megye|county)\s+([A-ZÁÉÍÓÖŐÚÜŰ][\wÁÉÍÓÖŐÚÜŰáéíóöőúüű-]+)",
        re.IGNORECASE,
    )
    _PREDICATE_CAND = re.compile(r"\b(?:ki|mi)\s+(?:[a-záéíóöőúüű]+\s+)?([a-záéíóöőúüű]{3,})\b", re.IGNORECASE)
    _YEAR_MONTH = re.compile(r"\b(19\d{2}|2\d{3})-(0[1-9]|1[0-2])\b")
    _DATE = re.compile(r"\b(19\d{2}|2\d{3})-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])\b")
    _DATE_RANGE = re.compile(
        r"\b(19\d{2}|2\d{3})-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])\b\s*(?:-|/|között|és|to)\s*\b(19\d{2}|2\d{3})-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])\b",
        re.IGNORECASE,
    )
    _RANGE = re.compile(r"\b(19\d{2}|2\d{3})\s*[-/]\s*(19\d{2}|2\d{3})\b")
    _ATTR_WORDS = ("milyen", "tulajdons", "érték", "paraméter", "állapot")
    _REL_WORDS = ("kapcsolat", "viszony", "kivel", "mihez", "reláció")
    _TIMELINE_WORDS = ("időrend", "hogyan változott", "timeline", "korábban", "azután", "előtte", "utána")
    _COMPARE_WORDS = ("összehasonlít", "hasonlítsd össze", "össze", "különbség", "vs", "versus", "mint", "vagy")
    _STATUS_AT_TIME_WORDS = ("akkor mi volt", "akkor milyen", "adott időben", "ekkor")
    _PLACE_ONLY = re.compile(r"\b(?:budapest|debrecen|szeged|pécs|győr|miskolc)\b", re.IGNORECASE)
    _MONTH_WORDS = {
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
    _MONTH_PATTERN = re.compile(
        r"\b(19\d{2}|2\d{3})\s+("
        + "|".join(_MONTH_WORDS.keys())
        + r")\b",
        re.IGNORECASE,
    )
    _QUOTED = re.compile(r"['\"]([^'\"]{2,})['\"]")
    _ENTITY_STOPWORDS = {
        "Mi",
        "Ki",
        "Mit",
        "Mikor",
        "Hol",
        "Hogy",
        "Hogyan",
        "Milyen",
        "Melyik",
        "Mennyi",
        "Mekkora",
        "Mutasd",
        "Mondd",
    }
    _ENTITY_HEAVY_HINTS = ("ki ", "kik ", "kivel", "kikről", "melyik személy", "melyik cég")
    _PREDICATE_HEAVY_HINTS = ("dolgozik", "vezet", "kapcsolódik", "történt", "státusz", "állapot", "szerep")
    _RELATION_STRONG_HINTS = ("kapcsolata", "viszonya", "között", "kivel", "mihez", "hogyan kapcsolódik")
    _ATTRIBUTE_STRONG_HINTS = ("milyen", "mennyi", "mekkora", "státusza", "állapota", "értéke")
    _ACTIVITY_HINTS = ("mi történt", "mit csinált", "hol van", "hol dolgozik", "mikor történt")

    @staticmethod
    def _normalize_lexical_query_text(text: str) -> str:
        lowered = str(text or "").lower()
        cleaned = re.sub(r"[^\wáéíóöőúüű\s-]", " ", lowered, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned

    @staticmethod
    def _dedupe_keep_order(values: list[str], normalize_lower: bool = False) -> list[str]:
        out: list[str] = []
        seen: set[str] = set()
        for value in values:
            item = str(value or "").strip()
            if not item:
                continue
            key = item.lower() if normalize_lower else item
            if key in seen:
                continue
            seen.add(key)
            out.append(item)
        return out

    @classmethod
    def _collect_entities(cls, q: str) -> list[str]:
        entities = [x for x in cls._CAP_WORD.findall(q) if x not in cls._ENTITY_STOPWORDS]
        entities.extend([x.strip() for x in cls._QUOTED.findall(q) if x.strip()])
        return cls._dedupe_keep_order(entities)

    @classmethod
    def _collect_places(cls, q: str) -> list[str]:
        places = [m.group(1) for m in cls._PLACE_HINT.finditer(q)]
        places.extend(cls._PLACE_ONLY.findall(q))
        return cls._dedupe_keep_order(places)

    @classmethod
    def _collect_predicates(cls, q: str, q_low: str) -> list[str]:
        predicates = [m.group(1).lower() for m in cls._PREDICATE_CAND.finditer(q)]
        predicates.extend([w for w in cls._PREDICATE_HEAVY_HINTS if w in q_low])
        return cls._dedupe_keep_order(predicates, normalize_lower=True)

    @classmethod
    def _build_exact_phrases(cls, q: str, entities: list[str], places: list[str]) -> list[str]:
        phrases = [x.strip() for x in cls._QUOTED.findall(q) if x.strip()]
        phrases.extend([x for x in entities if " " in x.strip()])
        phrases.extend([x for x in places if " " in x.strip()])
        return cls._dedupe_keep_order(phrases, normalize_lower=True)

    @classmethod
    def _build_intent_signals(
        cls,
        q_low: str,
        entities: list[str],
        predicates: list[str],
        places: list[str],
        has_time_window: bool,
        comparison_targets: list[str],
        has_comparison_hint: bool,
    ) -> dict[str, float]:
        signals = {
            "comparison": 0.0,
            "timeline": 0.0,
            "status_at_time": 0.0,
            "activity": 0.0,
            "attribute": 0.0,
            "relation": 0.0,
            "summary": 0.15,
        }
        signals["comparison"] += 0.35 * sum(1 for w in cls._COMPARE_WORDS if w in q_low)
        if has_comparison_hint and len(comparison_targets) >= 2:
            signals["comparison"] += 0.55
        signals["timeline"] += 0.30 * sum(1 for w in cls._TIMELINE_WORDS if w in q_low)
        if has_time_window:
            signals["timeline"] += 0.18
        signals["status_at_time"] += 0.42 * sum(1 for w in cls._STATUS_AT_TIME_WORDS if w in q_low)
        if has_time_window and any(w in q_low for w in ("státusz", "állapot", "ekkor", "akkor")):
            signals["status_at_time"] += 0.20
        signals["activity"] += 0.30 * sum(1 for w in cls._ACTIVITY_HINTS if w in q_low)
        if predicates:
            signals["activity"] += 0.08
        signals["attribute"] += 0.30 * sum(1 for w in cls._ATTRIBUTE_STRONG_HINTS if w in q_low)
        signals["relation"] += 0.30 * sum(1 for w in cls._RELATION_STRONG_HINTS if w in q_low)
        if has_comparison_hint and len(entities) >= 2:
            signals["relation"] += 0.12
            signals["comparison"] += 0.10
        if places:
            signals["activity"] += 0.06
        return signals

    @classmethod
    def _detect_comparison_targets(cls, q: str, q_low: str, entities: list[str], places: list[str]) -> list[str]:
        if not any(word in q_low for word in cls._COMPARE_WORDS):
            return []
        targets = entities[:2]
        if len(targets) >= 2:
            return targets
        for sep in (" vs ", " versus ", " és ", " vagy "):
            if sep in q_low:
                parts = [x.strip(" ,.?") for x in re.split(re.escape(sep.strip()), q, maxsplit=1) if x.strip(" ,.?")]
                if len(parts) >= 2:
                    raw_targets = parts[:2]
                    return cls._dedupe_keep_order(
                        [x for x in raw_targets if x and x not in places]
                    )[:2]
        return targets

    @classmethod
    def _resolve_retrieval_mode(
        cls,
        intent: str,
        entity_heavy: bool,
        predicate_heavy: bool,
        has_place_focus: bool,
        has_time_window: bool,
    ) -> tuple[str, str]:
        if intent == "comparison":
            return "comparison_first", "comparison intent"
        if intent in {"timeline", "status_at_time"}:
            return "timeline_first", "timeline/status intent"
        if entity_heavy:
            return "entity_first", "entity-heavy parse"
        if predicate_heavy and has_time_window:
            return "timeline_first", "predicate + valid_time focus"
        if has_place_focus and predicate_heavy:
            return "assertion_first", "place + predicate focus"
        if intent in {"attribute", "relation"}:
            return "entity_first", "attribute/relation intent"
        return "assertion_first", "default summary/activity"

    @staticmethod
    def _build_time_window(q: str, years: list[str]) -> tuple[datetime | None, datetime | None]:
        q_low = (q or "").lower()
        now = datetime.now(UTC).replace(tzinfo=None)
        date_range_match = QueryParser._DATE_RANGE.findall(q)
        if date_range_match:
            y1, m1, d1, y2, m2, d2 = date_range_match[0]
            start = datetime(int(y1), int(m1), int(d1), 0, 0, 0)
            end = datetime(int(y2), int(m2), int(d2), 23, 59, 59)
            return (start, end) if start <= end else (end, start)
        if "jelenleg" in q_low or "most" in q_low:
            start = datetime(now.year, now.month, 1, 0, 0, 0)
            if now.month == 12:
                end = datetime(now.year, 12, 31, 23, 59, 59)
            else:
                end = datetime(now.year, now.month + 1, 1, 0, 0, 0) - timedelta(seconds=1)
            return start, end
        if "idén" in q_low:
            return datetime(now.year, 1, 1, 0, 0, 0), datetime(now.year, 12, 31, 23, 59, 59)
        if "tavaly" in q_low:
            y = now.year - 1
            return datetime(y, 1, 1, 0, 0, 0), datetime(y, 12, 31, 23, 59, 59)
        range_match = QueryParser._RANGE.findall(q)
        if range_match:
            y1, y2 = range_match[0]
            start_year = min(int(y1), int(y2))
            end_year = max(int(y1), int(y2))
            return datetime(start_year, 1, 1, 0, 0, 0), datetime(end_year, 12, 31, 23, 59, 59)
        date_match = QueryParser._DATE.findall(q)
        if date_match:
            y, m, d = date_match[0]
            start = datetime(int(y), int(m), int(d), 0, 0, 0)
            end = datetime(int(y), int(m), int(d), 23, 59, 59)
            return start, end
        ym_match = QueryParser._YEAR_MONTH.findall(q)
        if ym_match:
            y, m = ym_match[0]
            start = datetime(int(y), int(m), 1, 0, 0, 0)
            if int(m) == 12:
                end = datetime(int(y), 12, 31, 23, 59, 59)
            else:
                next_month = datetime(int(y), int(m) + 1, 1, 0, 0, 0)
                end = next_month - timedelta(seconds=1)
            return start, end
        month_word_match = QueryParser._MONTH_PATTERN.findall(q_low)
        if len(month_word_match) >= 2 and any(x in q_low for x in ("között", " és ", "-")):
            y1, month_word_1 = month_word_match[0]
            y2, month_word_2 = month_word_match[-1]
            month_1 = QueryParser._MONTH_WORDS.get(month_word_1.lower())
            month_2 = QueryParser._MONTH_WORDS.get(month_word_2.lower())
            if month_1 is not None and month_2 is not None:
                start = datetime(int(y1), int(month_1), 1, 0, 0, 0)
                if int(month_2) == 12:
                    end = datetime(int(y2), 12, 31, 23, 59, 59)
                else:
                    end = datetime(int(y2), int(month_2) + 1, 1, 0, 0, 0) - timedelta(seconds=1)
                return (start, end) if start <= end else (end, start)
        if month_word_match:
            y, month_word = month_word_match[0]
            month = QueryParser._MONTH_WORDS.get(month_word.lower())
            if month is not None:
                start = datetime(int(y), int(month), 1, 0, 0, 0)
                if month == 12:
                    end = datetime(int(y), 12, 31, 23, 59, 59)
                else:
                    end = datetime(int(y), int(month) + 1, 1, 0, 0, 0) - timedelta(seconds=1)
                return start, end
        if years:
            year = int(years[0])
            return datetime(year, 1, 1, 0, 0, 0), datetime(year, 12, 31, 23, 59, 59)
        return None, None

    def parse(self, question: str) -> dict:
        """Intent + filter seed mezők kinyerése kérdésből."""
        q = (question or "").strip()
        q_low = q.lower()
        entities = self._collect_entities(q)
        years = self._YEAR.findall(q)
        places = self._collect_places(q)
        predicates = self._collect_predicates(q, q_low)
        query_from, query_to = self._build_time_window(q, years)
        relation_candidates = self._dedupe_keep_order([w for w in self._REL_WORDS if w in q_low], normalize_lower=True)
        attribute_candidates = self._dedupe_keep_order([w for w in self._ATTR_WORDS if w in q_low], normalize_lower=True)
        comparison_targets = self._detect_comparison_targets(q, q_low, entities, places)
        has_time_window = bool(query_from or query_to)
        has_comparison_hint = any(word in q_low for word in self._COMPARE_WORDS)
        intent_signals = self._build_intent_signals(
            q_low=q_low,
            entities=entities,
            predicates=predicates,
            places=places,
            has_time_window=has_time_window,
            comparison_targets=comparison_targets,
            has_comparison_hint=has_comparison_hint,
        )
        intent = max(intent_signals.items(), key=lambda x: x[1])[0]
        if intent == "summary" and any(k in q_low for k in self._COMPARE_WORDS):
            intent = "comparison"
        if intent == "summary" and any(k in q_low for k in self._TIMELINE_WORDS):
            intent = "timeline"
        comparison_time_windows = [years[:1], years[1:2]] if intent == "comparison" and len(years) >= 2 else []
        rare_entity_boost = 1.0 if any(len(x) >= 8 for x in entities) else 0.0
        entity_heavy = (len(entities) >= 2) or (rare_entity_boost > 0.0) or any(h in q_low for h in self._ENTITY_HEAVY_HINTS)
        predicate_heavy = len(predicates) >= 2 or len(relation_candidates) >= 1 or any(h in q_low for h in self._PREDICATE_HEAVY_HINTS)
        retrieval_mode, retrieval_mode_reason = self._resolve_retrieval_mode(
            intent=intent,
            entity_heavy=entity_heavy,
            predicate_heavy=predicate_heavy,
            has_place_focus=bool(places),
            has_time_window=has_time_window,
        )
        query_embedding_text = " | ".join(
            [
                self._normalize_lexical_query_text(q),
                f"intent={intent}",
                f"entities={','.join(entities)}",
                f"valid_time={query_from.date().isoformat() if query_from else ''}..{query_to.date().isoformat() if query_to else ''}",
                f"places={','.join(sorted(set(places)))}",
                f"predicates={','.join(sorted(set(predicates)))}",
            ]
        ).strip(" |")
        normalized_query_text = " ".join(
            [
                q_low,
                " ".join(sorted(set(predicates))),
                " ".join(sorted(set(places))),
                " ".join(sorted(set(entities))).lower(),
                " ".join(sorted(set(relation_candidates))),
                " ".join(sorted(set(attribute_candidates))),
            ]
        ).strip()
        lexical_query_text = self._normalize_lexical_query_text(normalized_query_text or q_low)
        exact_phrase_candidates = self._build_exact_phrases(q, entities, places)
        rare_entity_terms = [
            str(x).strip().lower()
            for x in entities
            if len(str(x).strip()) >= 8 or any(ch.isdigit() for ch in str(x))
        ]
        lexical_focus_terms = self._dedupe_keep_order(
            [str(x).strip().lower() for x in entities + places + predicates + relation_candidates + attribute_candidates if str(x).strip()],
            normalize_lower=True,
        )
        focus_axes = {
            "entity": round(min(1.0, 0.28 * len(entities) + (0.28 if entity_heavy else 0.0)), 2),
            "valid_time": round(min(1.0, 0.55 if has_time_window else 0.0), 2),
            "place": round(min(1.0, 0.35 * len(places)), 2),
            "predicate": round(min(1.0, 0.25 * len(predicates) + (0.20 if predicate_heavy else 0.0)), 2),
            "relation": round(min(1.0, 0.35 * len(relation_candidates)), 2),
            "attribute": round(min(1.0, 0.35 * len(attribute_candidates)), 2),
        }
        parser_audit = {
            "intent_signals": {k: round(float(v), 3) for k, v in intent_signals.items()},
            "focus_axes": focus_axes,
            "retrieval_mode_reason": retrieval_mode_reason,
            "comparison_target_count": len(comparison_targets),
            "has_valid_time_window": has_time_window,
            "entity_heavy": entity_heavy,
            "predicate_heavy": predicate_heavy,
            "rare_entity_terms": rare_entity_terms,
            "exact_phrase_candidates": exact_phrase_candidates,
        }

        return {
            "raw_query": q,
            "intent": intent,
            "entity_candidates": entities,
            "resolved_entity_candidates": {},
            "resolved_entity_ids": {},
            "time_candidates": years,
            # Valid-time ablak (query-ben megadott idő kizárólag assertion valid_time-ra vonatkozik)
            "query_valid_time_from": query_from,
            "query_valid_time_to": query_to,
            # Backward-compatible alias: belső logikában a valid_time_* az elsődleges.
            "query_time_from": query_from,
            "query_time_to": query_to,
            "valid_time_window": {
                "from": query_from.isoformat() if query_from else None,
                "to": query_to.isoformat() if query_to else None,
            },
            # Backward-compatible alias a régi time_window kulcshoz.
            "time_window": {
                "from": query_from.isoformat() if query_from else None,
                "to": query_to.isoformat() if query_to else None,
            },
            "place_candidates": sorted(set(places)),
            "resolved_place_candidates": [
                {
                    "raw_term": str(p),
                    "normalized_key": str(p).strip().lower(),
                    "resolution_source": "parser",
                }
                for p in sorted(set(places))
                if str(p).strip()
            ],
            "predicate_candidates": sorted(set(predicates)),
            "attribute_candidates": sorted(set(attribute_candidates)),
            "relation_candidates": sorted(set(relation_candidates)),
            "comparison_targets": comparison_targets,
            "comparison_time_windows": comparison_time_windows,
            "retrieval_mode": retrieval_mode,
            "query_embedding_text": query_embedding_text,
            "query_embedding_vector": None,
            "query_embedding_cache_key": " ".join(query_embedding_text.lower().split()),
            "query_embedding_time_ms": 0.0,
            "normalized_query_text": normalized_query_text,
            "lexical_query_text": lexical_query_text,
            "exact_phrase_candidates": exact_phrase_candidates,
            "lexical_focus_terms": lexical_focus_terms,
            "rare_entity_terms": rare_entity_terms,
            "hybrid_profile": {
                "entity_heavy": entity_heavy,
                "predicate_heavy": predicate_heavy,
                "relation_heavy": bool(relation_candidates),
                "attribute_heavy": bool(attribute_candidates),
                "rare_entity_terms": rare_entity_terms,
                "exact_phrase_candidates": exact_phrase_candidates,
            },
            "entity_heavy": entity_heavy,
            "predicate_heavy": predicate_heavy,
            "rare_entity_boost": rare_entity_boost,
            "focus_axes": focus_axes,
            "parser_audit": parser_audit,
        }
