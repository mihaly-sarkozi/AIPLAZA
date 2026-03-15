from __future__ import annotations

import re
from datetime import datetime, timedelta

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

    @staticmethod
    def _build_time_window(q: str, years: list[str]) -> tuple[datetime | None, datetime | None]:
        q_low = (q or "").lower()
        now = datetime.utcnow()
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
        if any(k in q_low for k in self._COMPARE_WORDS):
            intent = "comparison"
        elif any(k in q_low for k in self._TIMELINE_WORDS):
            intent = "timeline"
        elif any(k in q_low for k in self._STATUS_AT_TIME_WORDS):
            intent = "status_at_time"
        elif any(k in q_low for k in ["mi történt", "mit csinált", "mikor történt"]):
            intent = "activity"
        elif any(k in q_low for k in self._ATTR_WORDS):
            intent = "attribute"
        elif any(k in q_low for k in self._REL_WORDS):
            intent = "relation"
        else:
            intent = "summary"

        entities = sorted(set(self._CAP_WORD.findall(q)))
        years = self._YEAR.findall(q)
        places = [m.group(1) for m in self._PLACE_HINT.finditer(q)]
        places.extend(self._PLACE_ONLY.findall(q))
        predicates = [m.group(1).lower() for m in self._PREDICATE_CAND.finditer(q)]
        query_from, query_to = self._build_time_window(q, years)
        relation_candidates = [w for w in self._REL_WORDS if w in q_low]
        attribute_candidates = [w for w in self._ATTR_WORDS if w in q_low]
        comparison_targets = entities[:2] if intent == "comparison" else []
        if intent == "comparison" and (not comparison_targets or len(comparison_targets) < 2):
            for sep in (" vs ", " versus ", " és ", " vagy "):
                if sep in q_low:
                    parts = [x.strip() for x in q.split(sep.strip()) if x.strip()]
                    if len(parts) >= 2:
                        comparison_targets = parts[:2]
                        break
        comparison_time_windows = [years[:1], years[1:2]] if intent == "comparison" and len(years) >= 2 else []
        retrieval_mode = {
            "activity": "assertion_first",
            "attribute": "entity_first",
            "relation": "entity_first",
            "summary": "assertion_first",
            "timeline": "timeline_first",
            "comparison": "comparison_first",
            "status_at_time": "timeline_first",
        }.get(intent, "assertion_first")
        query_embedding_text = " | ".join(
            [
                q,
                f"intent={intent}",
                f"entities={','.join(entities)}",
                f"time={query_from.date().isoformat() if query_from else ''}..{query_to.date().isoformat() if query_to else ''}",
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
            ]
        ).strip()
        rare_entity_boost = 1.0 if any(len(x) >= 8 for x in entities) else 0.0
        entity_heavy = (len(entities) >= 2) or (rare_entity_boost > 0.0)
        predicate_heavy = len(predicates) >= 2 or len(relation_candidates) >= 1

        return {
            "raw_query": q,
            "intent": intent,
            "entity_candidates": entities,
            "resolved_entity_candidates": [],
            "time_candidates": years,
            "query_time_from": query_from,
            "query_time_to": query_to,
            "time_window": {
                "from": query_from.isoformat() if query_from else None,
                "to": query_to.isoformat() if query_to else None,
            },
            "place_candidates": sorted(set(places)),
            "resolved_place_candidates": [],
            "predicate_candidates": sorted(set(predicates)),
            "attribute_candidates": sorted(set(attribute_candidates)),
            "relation_candidates": sorted(set(relation_candidates)),
            "comparison_targets": comparison_targets,
            "comparison_time_windows": comparison_time_windows,
            "retrieval_mode": retrieval_mode,
            "query_embedding_text": query_embedding_text,
            "normalized_query_text": normalized_query_text,
            "entity_heavy": entity_heavy,
            "predicate_heavy": predicate_heavy,
            "rare_entity_boost": rare_entity_boost,
        }
