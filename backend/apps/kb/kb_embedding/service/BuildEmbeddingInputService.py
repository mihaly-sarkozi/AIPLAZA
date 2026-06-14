from __future__ import annotations

from apps.kb.kb_embedding.dto.EmbeddingChunkDto import EmbeddingChunkDto
from apps.kb.kb_embedding.dto.EmbeddingDiscoveryBundleDto import EmbeddingDiscoveryBundleDto
from apps.kb.kb_embedding.dto.EmbeddingInputDto import EmbeddingInputDto
from shared.utils.hash import sha256_text

_TOP_KEYWORDS = 8
_TOP_TOPICS = 5
_TOP_ENTITIES = 10
_TOP_PROCESS_STEPS = 3


class BuildEmbeddingInputService:
    def build(
        self,
        chunk: EmbeddingChunkDto,
        bundle: EmbeddingDiscoveryBundleDto | None,
        *,
        title: str,
    ) -> EmbeddingInputDto:
        lines: list[str] = []
        heading = bundle.heading_path if bundle and bundle.heading_path else title
        if heading:
            lines.append(f"Cím: {heading}")
        content_type = bundle.content_type if bundle else chunk.chunk_type
        if content_type:
            lines.append(f"Tartalomtípus: {content_type}")
        language = bundle.language_code if bundle else chunk.language_code
        if language:
            lines.append(f"Nyelv: {language}")
        lines.append("Szöveg:")
        lines.append(chunk.text.strip())
        if bundle and bundle.keywords:
            lines.append(f"Kulcsszavak: {', '.join(bundle.keywords)}")
        if bundle and bundle.topics:
            lines.append(f"Témák: {', '.join(bundle.topics)}")
        if bundle and bundle.entities:
            lines.append(f"Entitások: {', '.join(bundle.entities)}")
        if bundle and bundle.process_steps:
            for step in bundle.process_steps:
                lines.append(f"Folyamatlépés: {step}")
        input_text = "\n".join(lines).strip()
        content_hash = sha256_text(chunk.text.strip())
        input_hash = sha256_text(input_text)
        return EmbeddingInputDto(
            chunk_id=chunk.chunk_id,
            input_text=input_text,
            input_hash=input_hash,
            content_hash=content_hash,
        )

    @staticmethod
    def select_bundle_fields(bundle: EmbeddingDiscoveryBundleDto) -> EmbeddingDiscoveryBundleDto:
        return EmbeddingDiscoveryBundleDto(
            chunk_id=bundle.chunk_id,
            language_code=bundle.language_code,
            content_type=bundle.content_type,
            section_title=bundle.section_title,
            heading_path=bundle.heading_path,
            keywords=tuple(bundle.keywords[:_TOP_KEYWORDS]),
            topics=tuple(bundle.topics[:_TOP_TOPICS]),
            entities=tuple(bundle.entities[:_TOP_ENTITIES]),
            process_steps=tuple(bundle.process_steps[:_TOP_PROCESS_STEPS]),
        )


__all__ = ["BuildEmbeddingInputService"]
