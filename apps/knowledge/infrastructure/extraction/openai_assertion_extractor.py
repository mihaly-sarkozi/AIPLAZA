from __future__ import annotations

import json
from typing import Any

from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from apps.knowledge.ports.assertion_extractor_port import AssertionExtractorPort
from config.settings import settings


class ExtractionEntity(BaseModel):
    canonical_name: str
    entity_type: str
    aliases: list[str] = Field(default_factory=list)
    confidence: float = 0.0


class ExtractionAssertion(BaseModel):
    subject: str
    predicate: str
    object: str | None = None
    object_entity: str | None = None
    source_sentence_index: int | None = None
    subject_is_implicit: bool = False
    time_from: str | None = None
    time_to: str | None = None
    place_key: str | None = None
    attributes: list[dict[str, Any]] = Field(default_factory=list)
    canonical_text: str
    confidence: float = 0.0


class ExtractionEnvelope(BaseModel):
    entities: list[ExtractionEntity] = Field(default_factory=list)
    assertions: list[ExtractionAssertion] = Field(default_factory=list)
    mentions: list[dict[str, Any]] = Field(default_factory=list)
    time_candidates: list[dict[str, Any]] = Field(default_factory=list)
    place_candidates: list[dict[str, Any]] = Field(default_factory=list)
    extraction_confidence: float = 0.0


class OpenAIAssertionExtractor(AssertionExtractorPort):
    """LLM-alapú struktúrált extraction sanitized szövegre."""

    def __init__(self, client: AsyncOpenAI | None = None):
        self.client = client or AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    async def extract(self, sanitized_text: str, title: str | None = None) -> dict:
        """Sanitized szövegből entities + assertions kivonat."""
        prompt = (
            "Feladat: készíts strukturált knowledge kivonatot JSON-ban. "
            "Csak a megadott sanitized tartalmat használd, ne találj ki új tényt. "
            "Output JSON mezők: entities[], assertions[], mentions[], time_candidates[], place_candidates[], extraction_confidence. "
            "Az assertions elemeknél add vissza a source_sentence_index mezőt is (0-based), ha meghatározható. "
            "Az assertions time_from/time_to mezőit ISO formátumban add vissza, ha vannak. "
            "Ha az alany rejtett, az assertion subject_is_implicit=true legyen, és a mentions tömbben külön mention "
            "jelenjen meg surface_form='<implicit_subject>' és mention_type='implicit_subject' értékkel. "
            "A mentions elemekben add meg: surface_form, mention_type, grammatical_role, sentence_local_index, "
            "char_start, char_end, resolved_entity_candidate_name, resolution_confidence, is_implicit_subject, source_sentence_index."
        )
        user_content = {
            "title": title or "",
            "text": sanitized_text,
        }
        response = await self.client.chat.completions.create(
            model="gpt-4o-mini",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": json.dumps(user_content, ensure_ascii=False)},
            ],
            temperature=0.1,
        )
        content = response.choices[0].message.content or "{}"
        parsed = json.loads(content)
        envelope = ExtractionEnvelope(**parsed)
        return envelope.model_dump()
