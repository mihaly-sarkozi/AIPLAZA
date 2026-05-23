# backend/apps/knowledge/service/mention_resolution_service.py
# Resolves sentence mentions by combining extractor output with local heuristics.

from __future__ import annotations

import re
from dataclasses import replace

from apps.knowledge.domain.mention import Mention
from apps.knowledge.domain.sentence import Sentence
from apps.knowledge.service.mention_extractor import MentionExtractor


class MentionResolutionService:
    def __init__(self, *, mention_extractor: MentionExtractor | None = None) -> None:
        self._mention_extractor = mention_extractor or MentionExtractor()

    @staticmethod
    def mention_patterns() -> list[tuple[str, str]]:
        return [
            (
                "address",
                r"\b(?:ES-|HU-|DE-|FR-|IT-|PT-|RO-|PL-|AT-)?\d{4,5}\s+[A-ZÁÉÍÓÖŐÚÜŰ][\wÁÉÍÓÖŐÚÜŰáéíóöőúüű'’.\-]+(?:\s+[A-ZÁÉÍÓÖŐÚÜŰ][\wÁÉÍÓÖŐÚÜŰáéíóöőúüű'’.\-]+){0,3},?\s+(?:utca|u\.|út|útja|tér|köz|körút|lane|street|st\.|road|rd\.|avenue|ave\.|boulevard|blvd\.|calle|avenida|avda\.|plaza|piazza|via|straße|strasse|str\.|gasse|platz)\s+\d+[A-Za-z]?(?:/\d+)?(?:,?\s*(?:fszt\.?|emelet|em\.|ajtó|door|floor|apto\.?|apt\.?|wohnung|piso)\s*[\w/-]+)?\b",
            ),
            (
                "address",
                r"\b(?:Calle|Avenida|Avda\.|Plaza|Passeig|Via|Rue|Boulevard|Straße|Strasse|Street|Road|Avenue)\s+[A-ZÁÉÍÓÖŐÚÜŰ\wÁÉÍÓÖŐÚÜŰáéíóöőúüű'’.\-]+(?:\s+[A-ZÁÉÍÓÖŐÚÜŰ\wÁÉÍÓÖŐÚÜŰáéíóöőúüű'’.\-]+){0,5}\s+\d+[A-Za-z]?(?:/\d+)?(?:,?\s*(?:\d{4,5}\s+[A-ZÁÉÍÓÖŐÚÜŰ][\wÁÉÍÓÖŐÚÜŰáéíóöőúüű'’.\-]+(?:\s+[A-ZÁÉÍÓÖŐÚÜŰ][\wÁÉÍÓÖŐÚÜŰáéíóöőúüű'’.\-]+){0,3}))?(?:,?\s*(?:España|Spain|Hungary|Magyarország|Deutschland|Germany|France|Italia|Portugal|Polska|Romania|Austria))?\b",
            ),
            ("email", r"\b[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}\b"),
            ("phone_number", r"(?:(?<=\s)|^)(?:\+36|06)[\s\-()]?\d{1,2}[\s\-()]?\d{3}[\s\-()]?\d{3,4}(?=\s|$|[.,;])"),
            ("phone_number", r"(?:(?<=\s)|^)\+\d{2,3}[\s\-()]?\d{1,4}(?:[\s\-()]?\d{2,4}){2,4}(?=\s|$|[.,;])"),
            ("birth_date", r"\b(?:19|20)\d{2}\s*[./-]\s*(?:0?[1-9]|1[0-2])\s*[./-]\s*(?:0?[1-9]|[12]\d|3[01])\.?\b"),
            ("birth_date", r"\b(?:0?[1-9]|[12]\d|3[01])\s*[./-]\s*(?:0?[1-9]|1[0-2])\s*[./-]\s*(?:19|20)\d{2}\.?\b"),
            ("tax_id", r"\b\d{8}-\d-\d{2}\b"),
            ("spanish_nif", r"\b\d{8}[A-HJ-NP-TV-Z]\b"),
            ("spanish_nie", r"\b[XYZ]\d{7}[A-HJ-NP-TV-Z]\b"),
            ("spanish_cif", r"\b[A-HJNPQRSUVW]\d{7}[0-9A-J]\b"),
            (
                "eu_vat_number",
                r"\b(?:ATU\d{8}|BE0?\d{9}|BG\d{9,10}|CY\d{8}[A-Z]|CZ\d{8,10}|DE\d{9}|DK\d{8}|EE\d{9}|EL\d{9}|ES[A-Z0-9]\d{7}[A-Z0-9]|FI\d{8}|FR[A-HJ-NP-Z0-9]{2}\d{9}|HR\d{11}|HU\d{8}|IE\d[A-Z0-9*+]\d{5}[A-Z]{1,2}|IT\d{11}|LT(?:\d{9}|\d{12})|LU\d{8}|LV\d{11}|MT\d{8}|NL\d{9}B\d{2}|PL\d{10}|PT\d{9}|RO\d{2,10}|SE\d{12}|SI\d{8}|SK\d{10})\b",
            ),
            ("iban", r"\b[A-Z]{2}\d{2}(?:\s?[A-Z0-9]{4}){3,7}(?:\s?[A-Z0-9]{1,4})?\b"),
            ("bic_swift", r"\b[A-Z]{6}[A-Z0-9]{2}(?:[A-Z0-9]{3})?\b"),
            ("italian_codice_fiscale", r"\b[A-Z]{6}\d{2}[A-Z]\d{2}[A-Z]\d{3}[A-Z]\b"),
            ("french_siren", r"\b(?:SIREN[: ]*)?\d{9}\b"),
            ("french_siret", r"\b(?:SIRET[: ]*)?\d{14}\b"),
            ("polish_pesel", r"\b(?:PESEL[: ]*)?\d{11}\b"),
            ("romanian_cnp", r"\b(?:CNP[: ]*)?[1-8]\d{12}\b"),
            ("portuguese_nif", r"\b(?:NIF[: ]*)?\d{9}\b"),
            ("license_plate", r"\b[A-Z]{3}-\d{3}\b"),
            ("license_plate", r"\b[A-Z]{4}-\d{2}\b"),
            ("vin", r"\b[A-HJ-NPR-Z0-9]{17}\b"),
            ("traffic_permit_number", r"\b(?:forgalmi(?:\s+engedély)?\s*(?:szám|száma)?[: ]*)?[A-Z]{2}\d{6}\b"),
            ("driver_license_number", r"\b(?:jogosítvány(?:\s+szám|száma)?[: ]*)?[A-Z]{1,2}\d{6,8}\b"),
            ("social_security_number", r"\b\d{3}[ -]?\d{3}[ -]?\d{3}\b"),
            ("company_registration_number", r"\b\d{2}-\d{2}-\d{6}\b"),
            ("mixed_identifier", r"\b[A-Z0-9]{2,}(?:[-/][A-Z0-9]{2,})+\b"),
            ("mixed_identifier", r"\b[A-Z]{1,4}\d{2,}[A-Z0-9]*\b"),
            ("document_reference", r"\b\d{4}\.\s*évi\s+[IVXLCDM]+\.\s*törvény\b"),
            (
                "document_reference",
                r"\b\d+(?:/[A-Z])?\.\s*§(?:\s*\(\d+[a-z]?\))?(?:\s*(?:bekezdés|bek\.?))?(?:\s*[a-z]\))?(?:\s*(?:pont|alpont))?",
            ),
            ("document_reference", r"\b\d+(?:\.\d+){1,5}\.\b"),
            ("role", r"\b(?:Megbízó|Alkusz|Biztosító|Szolgáltató|Felhasználó|Megrendelő|Adatkezelő)\b"),
            ("organization", r"\b[A-ZÁÉÍÓÖŐÚÜŰ][\w.-]+(?:\s+[A-ZÁÉÍÓÖŐÚÜŰ][\w.-]+)*\s+(?:Kft\.|Zrt\.|Nyrt\.|Bt\.|GmbH|Ltd\.|Inc\.)(?=\s|$|[,;:])"),
            ("organization", r"\b[A-ZÁÉÍÓÖŐÚÜŰ][\w.&-]+(?:\s+[A-ZÁÉÍÓÖŐÚÜŰ][\w.&-]+){0,4}\s+(?:Kft\.|Zrt\.|Nyrt\.|Bt\.|Kht\.|Kkt\.|Egyesület|Alapítvány|Nonprofit\s+Kft\.)(?=\s|$|[,;:])"),
            ("system", r"\b[\w-]*(?:rendszer|platform|api|portál|alkalmazás)[\w-]*\b"),
            ("rule", r"\b(?:törvény|rendelet|szabályzat|ÁSZF|szabály)\b"),
            ("place", r"\b(?:Magyarország|Budapest|Európai Unió|EU)\b"),
        ]

    def build_mentions_for_sentence(self, sentence: Sentence) -> list[Mention]:
        text = sentence.text_content
        mentions: list[Mention] = []
        seen_spans: set[tuple[int, int, str]] = set()

        def _overlaps_existing(char_start: int, char_end: int) -> bool:
            for existing_start, existing_end, _existing_type in seen_spans:
                if char_start < existing_end and char_end > existing_start:
                    return True
            return False

        for mention_type, pattern in self.mention_patterns():
            for match in re.finditer(pattern, text, flags=re.IGNORECASE):
                raw_match = match.group(0)
                if mention_type == "bic_swift" and raw_match.upper() != raw_match:
                    continue
                char_start = sentence.char_start + match.start()
                char_end = sentence.char_start + match.end()
                key = (char_start, char_end, mention_type)
                if key in seen_spans or _overlaps_existing(char_start, char_end):
                    continue
                seen_spans.add(key)
                normalized_value = raw_match.strip()
                if mention_type == "phone_number":
                    normalized_value = re.sub(r"\D+", "", normalized_value)
                elif mention_type in {
                    "spanish_nif",
                    "spanish_nie",
                    "spanish_cif",
                    "eu_vat_number",
                    "iban",
                    "bic_swift",
                    "italian_codice_fiscale",
                    "french_siren",
                    "french_siret",
                    "polish_pesel",
                    "romanian_cnp",
                    "portuguese_nif",
                    "birth_date",
                    "tax_id",
                    "license_plate",
                    "vin",
                    "traffic_permit_number",
                    "driver_license_number",
                    "social_security_number",
                    "company_registration_number",
                    "mixed_identifier",
                }:
                    normalized_value = normalized_value.upper()
                    if mention_type == "iban":
                        normalized_value = re.sub(r"\s+", "", normalized_value)
                mentions.append(
                    Mention(
                        tenant=sentence.tenant,
                        corpus_uuid=sentence.corpus_uuid,
                        source_id=sentence.source_id,
                        document_id=sentence.document_id,
                        sentence_id=sentence.id,
                        mention_type=mention_type,
                        text_content=raw_match,
                        normalized_value=normalized_value,
                        char_start=char_start,
                        char_end=char_end,
                        confidence=0.84
                        if mention_type in {"email", "phone_number", "birth_date", "tax_id", "vin", "iban", "eu_vat_number"}
                        else 0.78
                        if mention_type in {"document_reference", "role", "address"}
                        else 0.66,
                        metadata={"pattern": pattern},
                    )
                )

        for match in re.finditer(r"\b\d{5,}\b", text):
            raw_value = match.group(0)
            numeric_value = int(raw_value)
            if numeric_value % 100 == 0:
                continue
            char_start = sentence.char_start + match.start()
            char_end = sentence.char_start + match.end()
            if _overlaps_existing(char_start, char_end):
                continue
            mention_type = "generic_identifier"
            seen_spans.add((char_start, char_end, mention_type))
            mentions.append(
                Mention(
                    tenant=sentence.tenant,
                    corpus_uuid=sentence.corpus_uuid,
                    source_id=sentence.source_id,
                    document_id=sentence.document_id,
                    sentence_id=sentence.id,
                    mention_type=mention_type,
                    text_content=raw_value,
                    normalized_value=raw_value,
                    char_start=char_start,
                    char_end=char_end,
                    confidence=0.52,
                    metadata={"heuristic": "numeric_identifier_ge_5_not_divisible_by_100"},
                )
            )

        for match in re.finditer(r"\b[A-ZÁÉÍÓÖŐÚÜŰ][a-záéíóöőúüű]+(?:\s+[A-ZÁÉÍÓÖŐÚÜŰ][a-záéíóöőúüű]+){1,2}\b", text):
            phrase = match.group(0)
            char_start = sentence.char_start + match.start()
            char_end = sentence.char_start + match.end()
            if any(existing.text_content == phrase for existing in mentions) or _overlaps_existing(char_start, char_end):
                continue
            mention_type = "person"
            if any(token in phrase for token in ("Kft", "Zrt", "Bt", "Nyrt")):
                mention_type = "organization"
            seen_spans.add((char_start, char_end, mention_type))
            mentions.append(
                Mention(
                    tenant=sentence.tenant,
                    corpus_uuid=sentence.corpus_uuid,
                    source_id=sentence.source_id,
                    document_id=sentence.document_id,
                    sentence_id=sentence.id,
                    mention_type=mention_type,
                    text_content=phrase,
                    normalized_value=phrase,
                    char_start=char_start,
                    char_end=char_end,
                    confidence=0.58,
                    metadata={"heuristic": "capitalized_phrase"},
                )
            )
        return mentions

    @staticmethod
    def align_extracted_mentions_to_sentence(sentence: Sentence, mentions: list[Mention]) -> list[Mention]:
        aligned: list[Mention] = []
        for item in mentions:
            aligned.append(
                replace(
                    item,
                    char_start=sentence.char_start + item.char_start,
                    char_end=sentence.char_start + item.char_end,
                    metadata={
                        **dict(item.metadata or {}),
                        "relative_char_start": item.char_start,
                        "relative_char_end": item.char_end,
                        "char_offset_mode": "sentence_relative_extractor_input",
                    },
                )
            )
        return aligned

    @staticmethod
    def merge_sentence_mentions(extracted_mentions: list[Mention], heuristic_mentions: list[Mention]) -> list[Mention]:
        merged: list[Mention] = []

        def _priority(item: Mention) -> tuple[int, int, int]:
            mention_type = str(item.mention_type or "")
            type_rank = {
                "location": 0,
                "module": 1,
                "software": 2,
                "process": 3,
                "organization": 4,
                "company": 4,
                "person": 5,
                "unknown": 9,
            }.get(mention_type, 8)
            return (type_rank, -(item.char_end - item.char_start), item.char_start)

        def _overlaps(left: Mention, right: Mention) -> bool:
            return left.char_start < right.char_end and left.char_end > right.char_start

        for item in [*extracted_mentions, *heuristic_mentions]:
            duplicate_idx = next(
                (
                    index
                    for index, existing in enumerate(merged)
                    if existing.text_content == item.text_content
                    and existing.char_start == item.char_start
                    and existing.char_end == item.char_end
                ),
                None,
            )
            if duplicate_idx is not None:
                if _priority(item) < _priority(merged[duplicate_idx]):
                    merged[duplicate_idx] = item
                continue
            shadowed_by: int | None = None
            should_skip = False
            for index, existing in enumerate(merged):
                if not _overlaps(item, existing):
                    continue
                if _priority(existing) <= _priority(item):
                    should_skip = True
                    break
                shadowed_by = index
                break
            if should_skip:
                continue
            if shadowed_by is not None:
                merged[shadowed_by] = item
            else:
                merged.append(item)
        return sorted(merged, key=lambda item: (item.char_start, item.char_end, item.text_content))

    def build_sentence_mentions(self, sentence: Sentence, *, language: str) -> list[Mention]:
        extracted_mentions = self.align_extracted_mentions_to_sentence(
            sentence,
            self._mention_extractor.extract(sentence, language=language),
        )
        heuristic_mentions = self.build_mentions_for_sentence(sentence)
        heuristic_mentions = [
            replace(
                item,
                metadata={
                    **dict(item.metadata or {}),
                    "language": language,
                },
            )
            for item in heuristic_mentions
        ]
        return self.merge_sentence_mentions(extracted_mentions, heuristic_mentions)


__all__ = ["MentionResolutionService"]
