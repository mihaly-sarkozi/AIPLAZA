from __future__ import annotations

import re

from apps.knowledge.domain.mention import Mention


class ClaimFrameDetector:
    @staticmethod
    def detect_assertion_mode(text: str) -> str:
        lowered = text.lower()
        if any(token in lowered for token in ("visszavon", "hatályon kívül", "érvényteleníti")):
            return "retraction"
        if any(token in lowered for token in ("helyesbít", "javít", "módosít", "pontosít")):
            return "correction"
        if any(token in lowered for token in ("talán", "valószínű", "feltételez", "elképzelhető")):
            return "uncertain"
        if any(token in lowered for token in ("vélemény", "szerintem", "úgy gondol", "megítélése")):
            return "opinion"
        if any(token in lowered for token in ("tervezi", "tervezett", "fog ", "majd ")) or " jövő" in lowered:
            return "plan"
        if any(token in lowered for token in ("nem ", "nincs", "tilos", "tagadja")):
            return "negation"
        if any(token in lowered for token in ("kell", "köteles", "jogosult", "felhatalmazza", "szükséges", "alkalmazandó", "kizárólag")):
            return "rule"
        if any(token in lowered for token in ("ha ", "amennyiben", "feltéve", "abban az esetben")):
            return "hypothesis"
        return "fact"

    @staticmethod
    def detect_time_framing(text: str, *, assertion_mode: str) -> tuple[str, str | None]:
        lowered = text.lower()
        year_match = re.search(r"\b(19|20)\d{2}\.", text)
        if any(token in lowered for token in ("jelenleg", "most", "aktuálisan")):
            return "current", "aktuális"
        if any(token in lowered for token in ("volt", "korábban", "előző", "megelőző")):
            return "past", year_match.group(0) if year_match else "múltbeli"
        if any(token in lowered for token in ("lesz", "jövő", "majd", "tervezi", "fog ")) or assertion_mode == "plan":
            return "future", year_match.group(0) if year_match else "jövőbeli"
        if year_match:
            return "event", year_match.group(0)
        if assertion_mode in {"rule", "negation"}:
            return "timeless", "általános szabály"
        return "unknown", None

    @staticmethod
    def detect_space_framing(text: str, mentions: list[Mention]) -> tuple[str, str | None]:
        lowered = text.lower()
        for mention in mentions:
            if mention.mention_type == "place":
                return "specific_place", mention.text_content
        if any(token in lowered for token in ("magyarország", "európai unió", "eu", "budapest")):
            return "jurisdiction", "Magyarország" if "magyarország" in lowered else "Európai Unió"
        if any(token in lowered for token in ("megállapodás", "szerződés", "megbízó", "alkusz", "társaság")):
            return "organization_scope", "szerződéses/organizációs tér"
        return "location_independent", None

    @staticmethod
    def detect_claim_type(text: str, *, assertion_mode: str, mentions: list[Mention]) -> str:
        lowered = text.lower()
        if any(token in lowered for token in ("azonosító", "adószám", "számlaszám", "id", "uuid")):
            return "identifier"
        if assertion_mode in {"rule", "negation"} or any(token in lowered for token in ("ha ", "amennyiben", "feltétel")):
            return "rule_condition"
        if assertion_mode == "opinion":
            return "evaluative"
        if any(token in lowered for token in ("történt", "bekövetkezik", "létrejön", "megszűnik", "küld", "rögzít")):
            return "event"
        if len([mention for mention in mentions if mention.mention_type in {"person", "organization", "role", "system"}]) >= 2:
            return "relational"
        if any(token in lowered for token in ("van", "áll", "érvényes", "fennáll")):
            return "state"
        if any(token in lowered for token in ("minősül", "jelenti", "tartalmazza", "leírása")):
            return "stable_descriptor"
        return "other"

    @staticmethod
    def detect_predicate(text: str) -> tuple[str, int]:
        predicate_patterns = [
            r"\b(felhatalmazza|köteles|jogosult|rögzítse|rögzíti|alkalmazandó|küldi|küld|lehet|kell|van|áll|minősül|érvényes|tervezi|visszavonja|módosítja)\b",
        ]
        for pattern in predicate_patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                return match.group(1), match.start()
        words = text.split()
        if len(words) >= 2:
            return words[1], text.find(words[1])
        return text.strip(), 0


__all__ = ["ClaimFrameDetector"]
