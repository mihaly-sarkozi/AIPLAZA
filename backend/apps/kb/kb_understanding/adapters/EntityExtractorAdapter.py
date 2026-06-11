from __future__ import annotations

# backend/apps/kb/kb_understanding/adapters/EntityExtractorAdapter.py
# Feladat: Entitáskinyerés chunkokból — LLM-alapú felismerés + determinisztikus
# regex-kiegészítés (dátum, szerződésszám, számlaszám, ticket azonosító).
# Sárközi Mihály - 2026.06.11

import re

from apps.kb.kb_understanding.adapters.LlmCompletionAdapter import LlmCompletionAdapter
from apps.kb.kb_understanding.config.UnderstandingConf import (
    DEFAULT_UNDERSTANDING_CONFIG,
    UnderstandingConfig,
)
from apps.kb.kb_understanding.dto.KnowledgeEntityDto import KnowledgeEntityDto
from apps.kb.kb_understanding.enums.EntityType import EntityType

_SYSTEM_PROMPT = (
    "Te egy tudástár entitáskinyerő komponense vagy. A kapott szövegrészekből entitásokat "
    "nyersz ki. Csak a következő típusokat használd: person, customer, company, project, "
    "product, system, process, document, contract_number, invoice_number, ticket_id, date, "
    "deadline, other. Kizárólag érvényes JSON-nal válaszolj, a következő formában: "
    '{"entities": [{"type": "...", "name": "...", "aliases": ["..."], '
    '"confidence": 0.0, "chunk_ids": ["..."]}]}. '
    "A confidence 0 és 1 közötti szám. Csak a szövegben ténylegesen szereplő entitásokat add vissza."
)

_REGEX_PATTERNS: tuple[tuple[EntityType, re.Pattern[str]], ...] = (
    (EntityType.DATE, re.compile(r"\b\d{4}[./-]\s?\d{1,2}[./-]\s?\d{1,2}\b\.?")),
    (EntityType.TICKET_ID, re.compile(r"\b[A-Z][A-Z0-9]{1,9}-\d{1,6}\b")),
    (EntityType.CONTRACT_NUMBER, re.compile(r"\b(?:SZERZ|SZ|CTR|K)[-/]?\d{2,4}[-/]\d{1,6}\b", re.IGNORECASE)),
    (EntityType.INVOICE_NUMBER, re.compile(r"\b(?:SZLA|INV)[-/]?\d{2,4}[-/]?\d{1,8}\b", re.IGNORECASE)),
)


class EntityExtractorAdapter:
    """``EntityExtractorInterface`` implementáció."""

    def __init__(
        self,
        llm: LlmCompletionAdapter,
        config: UnderstandingConfig = DEFAULT_UNDERSTANDING_CONFIG,
    ) -> None:
        self._llm = llm
        self._config = config

    def extract_entities(self, chunks: list[tuple[str, str]]) -> list[KnowledgeEntityDto]:
        merged: dict[tuple[str, str], KnowledgeEntityDto] = {}
        for batch in self._batches(chunks):
            for entity in self._extract_with_llm(batch):
                self._merge(merged, entity)
        for chunk_id, text in chunks:
            for entity in self._extract_with_regex(chunk_id, text):
                self._merge(merged, entity)
        return list(merged.values())

    def _batches(self, chunks: list[tuple[str, str]]) -> list[list[tuple[str, str]]]:
        batches: list[list[tuple[str, str]]] = []
        current: list[tuple[str, str]] = []
        current_chars = 0
        for chunk_id, text in chunks:
            if current and (
                len(current) >= self._config.llm_chunk_batch_size
                or current_chars + len(text) > self._config.llm_max_input_chars
            ):
                batches.append(current)
                current = []
                current_chars = 0
            current.append((chunk_id, text))
            current_chars += len(text)
        if current:
            batches.append(current)
        return batches

    def _extract_with_llm(self, batch: list[tuple[str, str]]) -> list[KnowledgeEntityDto]:
        user_prompt = "\n\n".join(
            f"[chunk_id={chunk_id}]\n{text}" for chunk_id, text in batch
        )
        payload = self._llm.complete_json(system=_SYSTEM_PROMPT, user=user_prompt)
        raw_entities = payload.get("entities", []) if isinstance(payload, dict) else []
        valid_chunk_ids = {chunk_id for chunk_id, _ in batch}
        entities: list[KnowledgeEntityDto] = []
        for raw in raw_entities:
            if not isinstance(raw, dict):
                continue
            entity = self._parse_entity(raw, valid_chunk_ids)
            if entity is not None:
                entities.append(entity)
        return entities

    @staticmethod
    def _parse_entity(raw: dict, valid_chunk_ids: set[str]) -> KnowledgeEntityDto | None:
        name = str(raw.get("name", "") or "").strip()
        if not name:
            return None
        type_value = str(raw.get("type", "") or "").strip().lower()
        try:
            entity_type = EntityType(type_value)
        except ValueError:
            entity_type = EntityType.OTHER
        try:
            confidence = float(raw.get("confidence", 0.5))
        except (TypeError, ValueError):
            confidence = 0.5
        confidence = min(1.0, max(0.0, confidence))
        aliases = tuple(
            str(alias).strip()
            for alias in (raw.get("aliases") or [])
            if str(alias).strip() and str(alias).strip() != name
        )
        chunk_ids = tuple(
            str(chunk_id).strip()
            for chunk_id in (raw.get("chunk_ids") or [])
            if str(chunk_id).strip() in valid_chunk_ids
        )
        return KnowledgeEntityDto(
            entity_type=entity_type,
            name=name,
            normalized_name=name.lower(),
            confidence=confidence,
            aliases=aliases,
            chunk_ids=chunk_ids,
        )

    @staticmethod
    def _extract_with_regex(chunk_id: str, text: str) -> list[KnowledgeEntityDto]:
        entities: list[KnowledgeEntityDto] = []
        for entity_type, pattern in _REGEX_PATTERNS:
            for match in pattern.finditer(text):
                name = match.group(0).strip()
                entities.append(
                    KnowledgeEntityDto(
                        entity_type=entity_type,
                        name=name,
                        normalized_name=name.lower(),
                        confidence=1.0,
                        chunk_ids=(chunk_id,),
                    )
                )
        return entities

    @staticmethod
    def _merge(
        merged: dict[tuple[str, str], KnowledgeEntityDto], entity: KnowledgeEntityDto
    ) -> None:
        key = (entity.entity_type.value, entity.normalized_name)
        existing = merged.get(key)
        if existing is None:
            merged[key] = entity
            return
        merged[key] = KnowledgeEntityDto(
            entity_type=existing.entity_type,
            name=existing.name,
            normalized_name=existing.normalized_name,
            confidence=max(existing.confidence, entity.confidence),
            aliases=tuple(dict.fromkeys(existing.aliases + entity.aliases)),
            chunk_ids=tuple(dict.fromkeys(existing.chunk_ids + entity.chunk_ids)),
        )


__all__ = ["EntityExtractorAdapter"]
