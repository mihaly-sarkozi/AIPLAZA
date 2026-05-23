# backend/apps/knowledge/qdrant/qdrant_wrapper.py
# Feladat: Qdrant kliens wrapper a knowledge retrieval/index műveletekhez. Collection schema kezelést, batch upsertet, filterezett keresést, fusion scoringot és törléseket orkessztrál; a lexical scoring helper logika külön modulba került. Program-specifikus Qdrant adapter.
# Sárközi Mihály - 2026.05.21

import logging

from qdrant_client import QdrantClient
from qdrant_client import models as qm
from qdrant_client.http.exceptions import ResponseHandlingException, UnexpectedResponse

_log = logging.getLogger(__name__)
from typing import Any
import asyncio
import uuid as uuid_lib
from apps.knowledge.ai.embedding_provider import EmbeddingProvider
from apps.knowledge.qdrant.filters import build_payload_filter
from apps.knowledge.qdrant.lexical import (
    expanded_lexical_tokens,
    lexical_tokens,
    near_exact_phrase_score,
    normalize_lexical_text,
    normalize_point_id,
    payload_lexical_text,
    rare_term_score,
    token_shape_boost,
    weighted_overlap_score,
)
from core.kernel.config.config_loader import settings


class QdrantUnavailableError(Exception):
    """Qdrant nem elérhető vagy a konfiguráció hibás (pl. 404)."""


class QdrantClientWrapper:
    # Ez a metódus a Python-specifikus speciális működést valósítja meg.
    def __init__(
        self,
        url: str,
        api_key: str,
        embedding_provider: EmbeddingProvider,
        timeout: int | None = None,
    ):
        client_kwargs: dict[str, Any] = {
            "url": url,
            "check_compatibility": False,
        }
        if str(api_key or "").strip():
            client_kwargs["api_key"] = api_key
        if timeout is not None:
            client_kwargs["timeout"] = int(timeout)
        self.client = QdrantClient(**client_kwargs)
        self.embedding_provider = embedding_provider
        self.embedding_model = str(getattr(embedding_provider, "model_key", "unknown"))
        self.vector_size = int(getattr(embedding_provider, "vector_size", 1024) or 1024)
        self._embedding_cache: dict[str, list[float]] = {}
        self._embedding_cache_order: list[str] = []
        self._embedding_cache_max = 64

    @staticmethod
    def _normalize_point_id(raw_id: Any, *, point_type: str | None = None) -> str:
        return normalize_point_id(raw_id, point_type=point_type)

    # Ez a metódus normalizálja a(z) lexical text logikáját.
    @staticmethod
    def _normalize_lexical_text(text: str) -> str:
        return normalize_lexical_text(text)

    # Ez a metódus a(z) expanded_lexical_tokens logikáját valósítja meg.
    @classmethod
    def _expanded_lexical_tokens(cls, text: str) -> list[str]:
        return expanded_lexical_tokens(text)

    # Ez a metódus a(z) lexical_tokens logikáját valósítja meg.
    @classmethod
    def _lexical_tokens(cls, text: str) -> list[str]:
        return lexical_tokens(text)

    # Ez a metódus a(z) token_shape_boost logikáját valósítja meg.
    @staticmethod
    def _token_shape_boost(token: str) -> float:
        return token_shape_boost(token)

    # Ez a metódus a(z) payload_lexical_text logikáját valósítja meg.
    @classmethod
    def _payload_lexical_text(cls, payload: dict[str, Any]) -> str:
        return payload_lexical_text(payload)

    # Ez a metódus a(z) near_exact_phrase_score logikáját valósítja meg.
    @classmethod
    def _near_exact_phrase_score(cls, query_text: str, payload_text: str) -> float:
        return near_exact_phrase_score(query_text, payload_text)

    # Ez a metódus a(z) weighted_overlap_score logikáját valósítja meg.
    @classmethod
    def _weighted_overlap_score(cls, query_tokens: list[str], text_tokens: list[str]) -> float:
        return weighted_overlap_score(query_tokens, text_tokens)

    # Ez a metódus a(z) rare_term_score logikáját valósítja meg.
    @classmethod
    def _rare_term_score(cls, rare_terms: list[str], payload_text: str, payload_tokens: list[str]) -> float:
        return rare_term_score(rare_terms, payload_text, payload_tokens)

    async def embed_text(self, text: str) -> list[float]:
        """Szöveg embedding generálása konfigurált providerrel."""
        normalized = " ".join(str(text or "").split())
        if len(normalized) > 12000:
            normalized = normalized[:12000]
        if normalized in self._embedding_cache:
            return list(self._embedding_cache[normalized])
        vector = await self.embedding_provider.embed_text(normalized)
        self._embedding_cache[normalized] = vector
        self._embedding_cache_order.append(normalized)
        if len(self._embedding_cache_order) > self._embedding_cache_max:
            oldest = self._embedding_cache_order.pop(0)
            self._embedding_cache.pop(oldest, None)
        return vector

    def ensure_collection_schema(
        self,
        collection_name: str,
        vector_size: int | None = None,
        distance: qm.Distance = qm.Distance.COSINE,
    ) -> None:
        """Collection létrehozása, ha még nincs."""
        target_size = int(vector_size or self.vector_size)

        # Ez a függvény a(z) exists logikáját valósítja meg.
        def _exists() -> bool:
            return self.client.collection_exists(collection_name=collection_name)

        try:
            exists = _exists()
        except Exception:
            exists = False

        if not exists:
            self.client.create_collection(
                collection_name=collection_name,
                vectors_config=qm.VectorParams(size=target_size, distance=distance),
            )
        # Gyakran szűrt payload mezőkre indexek (új és meglévő kollekciókra is).
        for field_name, schema in [
            ("point_type", qm.PayloadSchemaType.KEYWORD),
            ("kb_uuid", qm.PayloadSchemaType.KEYWORD),
            ("kb_id", qm.PayloadSchemaType.INTEGER),
            ("profile_id", qm.PayloadSchemaType.KEYWORD),
            ("entity_name", qm.PayloadSchemaType.KEYWORD),
            ("entity_type", qm.PayloadSchemaType.KEYWORD),
            ("claim_types", qm.PayloadSchemaType.KEYWORD),
            ("states", qm.PayloadSchemaType.KEYWORD),
            ("time_modes", qm.PayloadSchemaType.KEYWORD),
            ("source_point_id", qm.PayloadSchemaType.KEYWORD),
            ("source_sentence_id", qm.PayloadSchemaType.INTEGER),
            ("subject_entity_id", qm.PayloadSchemaType.INTEGER),
            ("entity_ids", qm.PayloadSchemaType.INTEGER),
            ("place_key", qm.PayloadSchemaType.KEYWORD),
            ("place_keys", qm.PayloadSchemaType.KEYWORD),
            ("place_hierarchy_keys", qm.PayloadSchemaType.KEYWORD),
            ("time_from", qm.PayloadSchemaType.DATETIME),
            ("time_to", qm.PayloadSchemaType.DATETIME),
        ]:
            try:
                self.client.create_payload_index(
                    collection_name=collection_name,
                    field_name=field_name,
                    field_schema=schema,
                )
            except Exception:
                # Index már létezik vagy backend nem támogatja: nem blokkoljuk.
                pass

    def ensure_collection(self, collection_name: str, vector_size: int | None = None) -> None:
        """Kompatibilis ensure alias tudástár retrievalhez."""
        self.ensure_collection_schema(
            collection_name=collection_name,
            vector_size=vector_size,
            distance=qm.Distance.COSINE,
        )

    def create_collection(self, name: str) -> None:
        """Új kollekció létrehozása Qdrant-ban (create, nem recreate – így nem 404 ha még nincs)."""
        try:
            self.ensure_collection_schema(name, vector_size=self.vector_size, distance=qm.Distance.COSINE)
        except UnexpectedResponse as e:
            if e.status_code == 404:
                raise QdrantUnavailableError(
                    "Qdrant 404: a szolgáltatás nem elérhető vagy a QDRANT_URL hibás. "
                    "Lokálisan pl. http://localhost:6333, Cloud-nál a cluster URL (trailing slash nélkül). "
                    "Ellenőrizd a .env-ben a QDRANT_URL-t és hogy a Qdrant fut-e."
                ) from e
            raise

    # Ez az aszinkron metódus biztosítja a(z) collection séma async logikáját.
    async def ensure_collection_schema_async(
        self,
        collection_name: str,
        vector_size: int | None = None,
    ) -> None:
        await asyncio.to_thread(self.ensure_collection_schema, collection_name, vector_size, qm.Distance.COSINE)

    async def upsert_vector(self, uuid: str, collection: str, vector: list[float], metadata: dict) -> Any:
        """Vektor beszúrása Qdrant kollekcióba (async wrapper sync hívásra)."""
        # Ez a függvény a(z) upsert logikáját valósítja meg.
        def _upsert():
            self.ensure_collection_schema(collection)
            return self.client.upsert(
                collection_name=collection,
                points=[{
                    "id": uuid,
                    "vector": vector,
                    "payload": metadata
                }]
            )
        return await asyncio.to_thread(_upsert)

    # Ez az aszinkron metódus a(z) upsert_points logikáját valósítja meg.
    async def _upsert_points(self, collection: str, points: list[dict[str, Any]]) -> Any:
        # Ez a függvény a(z) upsert_batch logikáját valósítja meg.
        def _upsert_batch(batch: list[dict[str, Any]]):
            self.ensure_collection_schema(collection)
            return self.client.upsert(collection_name=collection, points=batch)

        result = None
        batch_size = 128
        max_retries = 2  # 3 próbálkozás összesen
        for i in range(0, len(points), batch_size):
            batch = points[i : i + batch_size]
            for attempt in range(max_retries + 1):
                try:
                    result = await asyncio.to_thread(_upsert_batch, batch)
                    break
                except ResponseHandlingException as e:
                    src = getattr(e, "source", e)
                    msg = str(src).lower() if src else ""
                    if "timeout" in msg or "timed out" in msg:
                        if attempt < max_retries:
                            wait_sec = 2 * (attempt + 1)
                            _log.warning(
                                "Qdrant write timeout, retry %d/%d after %ds: %s",
                                attempt + 1,
                                max_retries,
                                wait_sec,
                                msg[:200],
                            )
                            await asyncio.sleep(wait_sec)
                        else:
                            raise
                    else:
                        raise
        return result

    async def batch_upsert_points(self, collection: str, points: list[dict[str, Any]]) -> Any:
        """Batch upsert wrapper későbbi bővítésekhez."""
        return await self._upsert_points(collection, points)

    # Ez az aszinkron metódus a(z) upsert_typed_points logikáját valósítja meg.
    async def _upsert_typed_points(self, collection: str, point_type: str, rows: list[dict[str, Any]]) -> None:
        points: list[dict[str, Any]] = []
        for row in rows:
            text_value = (row.get("text") or row.get("canonical_text") or row.get("canonical_name") or "").strip()
            if not text_value:
                continue
            vector = row.get("vector")
            if vector is None:
                vector = await self.embed_text(text_value)
            raw_point_id = row.get("id") or uuid_lib.uuid4()
            point_id = self._normalize_point_id(raw_point_id, point_type=point_type)
            payload = dict(row.get("payload") or {})
            payload["point_type"] = point_type
            payload.setdefault("text", text_value)
            payload.setdefault("external_point_id", str(raw_point_id))
            points.append(
                {
                    "id": point_id,
                    "vector": vector,
                    "payload": payload,
                }
            )
        if points:
            await self._upsert_points(collection, points)

    async def upsert_entity_points(self, collection: str, rows: list[dict[str, Any]]) -> None:
        """Entity pointok upsertje."""
        await self._upsert_typed_points(collection, "entity", rows)

    async def upsert_assertion_points(self, collection: str, rows: list[dict[str, Any]]) -> None:
        """Assertion pointok upsertje."""
        await self._upsert_typed_points(collection, "assertion", rows)

    async def upsert_sentence_points(self, collection: str, rows: list[dict[str, Any]]) -> None:
        """Sentence pointok upsertje."""
        await self._upsert_typed_points(collection, "sentence", rows)

    async def upsert_structural_chunk_points(self, collection: str, rows: list[dict[str, Any]]) -> None:
        """Structural chunk pointok upsertje."""
        await self._upsert_typed_points(collection, "structural_chunk", rows)

    async def upsert_retrieval_chunk_points(self, collection: str, rows: list[dict[str, Any]]) -> None:
        """RetrievalChunk pointok upsertje."""
        await self._upsert_typed_points(collection, "retrieval_chunk", rows)

    async def upsert_semantic_block_points(self, collection: str, rows: list[dict[str, Any]]) -> None:
        """SemanticBlock pointok upsertje."""
        await self._upsert_typed_points(collection, "semantic_block", rows)

    # Ez a metódus felépíti a(z) filter logikáját.
    def _build_filter(self, payload_filter: dict[str, Any] | None = None) -> qm.Filter | None:
        return build_payload_filter(payload_filter)

    async def search_points(
        self,
        collection: str,
        query: str | None = None,
        limit: int = 10,
        point_types: list[str] | None = None,
        payload_filter: dict[str, Any] | None = None,
        query_vector: list[float] | None = None,
        lexical_query: str | None = None,
        fusion_semantic_weight: float | None = None,
        fusion_lexical_weight: float | None = None,
        lexical_focus_terms: list[str] | None = None,
        exact_phrases: list[str] | None = None,
        rare_terms: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Dense similarity keresés payload filterrel + lexical/fusion score előkészítés."""
        if query_vector is None:
            query_text = str(query or "").strip()
            if not query_text:
                return []
            vector = await self.embed_text(query_text)
        else:
            vector = list(query_vector)
        used_precomputed_vector = query_vector is not None
        effective_filter = dict(payload_filter or {})
        if point_types:
            effective_filter["point_type"] = point_types
        flt = self._build_filter(effective_filter)

        # Ez a függvény a(z) search logikáját valósítja meg.
        def _search():
            self.ensure_collection_schema(collection)
            return self.client.search(
                collection_name=collection,
                query_vector=vector,
                query_filter=flt,
                limit=max(1, min(limit, 100)),
                with_payload=True,
                with_vectors=False,
            )

        raw = await asyncio.to_thread(_search)
        lexical_text = str(lexical_query or query or "")
        lexical_query_norm = self._normalize_lexical_text(lexical_text)
        q_tokens = self._lexical_tokens(lexical_text)
        q_token_set = set(q_tokens)
        focus_terms = {
            self._normalize_lexical_text(str(x))
            for x in (lexical_focus_terms or [])
            if self._normalize_lexical_text(str(x))
        }
        exact_phrase_terms = [
            self._normalize_lexical_text(str(x))
            for x in (exact_phrases or [])
            if self._normalize_lexical_text(str(x))
        ]
        q_bigrams = {
            f"{q_tokens[i]} {q_tokens[i + 1]}"
            for i in range(max(0, len(q_tokens) - 1))
        }
        rare_query_tokens = self._lexical_tokens(" ".join(rare_terms or [])) or [t for t in q_tokens if self._token_shape_boost(t) >= 0.75]
        semantic_raw_scores: list[float] = []
        lexical_raw_scores: list[float] = []
        rows: list[dict[str, Any]] = []
        for hit in raw:
            payload = dict(hit.payload or {})
            text_norm = self._payload_lexical_text(payload)
            lexical_score = 0.0
            lexical_features: dict[str, float] = {
                "token_overlap": 0.0,
                "weighted_token_overlap": 0.0,
                "jaccard": 0.0,
                "substring_score": 0.0,
                "bigram_overlap": 0.0,
                "phrase_score": 0.0,
                "near_exact_score": 0.0,
                "rare_score": 0.0,
                "focus_term_score": 0.0,
                "exact_phrase_score": 0.0,
            }
            if q_token_set and text_norm:
                text_tokens = self._lexical_tokens(text_norm)
                text_token_set = set(text_tokens)
                inter = q_token_set.intersection(text_token_set)
                union = q_token_set.union(text_token_set)
                token_overlap = len(inter) / max(1, len(q_token_set))
                weighted_token_overlap = self._weighted_overlap_score(q_tokens, text_tokens)
                jaccard = len(inter) / max(1, len(union))
                substring_hits = sum(1 for t in q_token_set if t in text_norm)
                substring_score = substring_hits / max(1, len(q_token_set))
                text_bigrams = {
                    f"{text_tokens[i]} {text_tokens[i + 1]}"
                    for i in range(max(0, len(text_tokens) - 1))
                }
                bigram_overlap = (
                    len(q_bigrams.intersection(text_bigrams)) / max(1, len(q_bigrams))
                    if q_bigrams else 0.0
                )
                phrase_score = 1.0 if lexical_query_norm and lexical_query_norm in text_norm else 0.0
                near_exact_score = self._near_exact_phrase_score(lexical_query_norm, text_norm)
                rare_score = self._rare_term_score(rare_query_tokens, text_norm, text_tokens)
                focus_hits = sum(1 for term in focus_terms if term and term in text_norm)
                focus_term_score = (
                    focus_hits / max(1, len(focus_terms))
                    if focus_terms else 0.0
                )
                exact_phrase_hits = sum(1 for phrase in exact_phrase_terms if phrase and phrase in text_norm)
                exact_phrase_score = (
                    exact_phrase_hits / max(1, len(exact_phrase_terms))
                    if exact_phrase_terms else 0.0
                )
                overlap_w = float(getattr(settings, "qdrant_lexical_overlap_weight", 0.72))
                substring_w = float(getattr(settings, "qdrant_lexical_substring_weight", 0.28))
                # Robusztusabb lexical komponens: token + exact phrase + rare token + ngram.
                lexical_score = (
                    (0.24 * token_overlap)
                    + (0.18 * weighted_token_overlap)
                    + (0.10 * ((overlap_w * token_overlap) + (substring_w * substring_score)))
                    + (0.10 * jaccard)
                    + (0.12 * bigram_overlap)
                    + (0.10 * phrase_score)
                    + (0.07 * near_exact_score)
                    + (0.05 * rare_score)
                    + (0.02 * focus_term_score)
                    + (0.02 * exact_phrase_score)
                )
                lexical_features = {
                    "token_overlap": float(token_overlap),
                    "weighted_token_overlap": float(weighted_token_overlap),
                    "jaccard": float(jaccard),
                    "substring_score": float(substring_score),
                    "bigram_overlap": float(bigram_overlap),
                    "phrase_score": float(phrase_score),
                    "near_exact_score": float(near_exact_score),
                    "rare_score": float(rare_score),
                    "focus_term_score": float(focus_term_score),
                    "exact_phrase_score": float(exact_phrase_score),
                }
            semantic = float(hit.score)
            semantic_raw_scores.append(semantic)
            lexical_raw_scores.append(float(max(0.0, min(1.0, lexical_score))))
            rows.append(
                {
                    "id": str(hit.id),
                    "score": semantic,
                    "semantic_score": semantic,
                    "lexical_score": float(max(0.0, min(1.0, lexical_score))),
                    "used_precomputed_query_vector": used_precomputed_vector,
                    "lexical_features": lexical_features,
                    "payload": payload,
                }
            )
        if not rows:
            return []
        sem_min, sem_max = min(semantic_raw_scores), max(semantic_raw_scores)
        lex_min, lex_max = min(lexical_raw_scores), max(lexical_raw_scores)
        semantic_w = float(
            fusion_semantic_weight
            if fusion_semantic_weight is not None
            else getattr(settings, "qdrant_fusion_semantic_weight", 0.72)
        )
        lexical_w = float(
            fusion_lexical_weight
            if fusion_lexical_weight is not None
            else getattr(settings, "qdrant_fusion_lexical_weight", 0.28)
        )
        total_w = max(1e-9, semantic_w + lexical_w)
        semantic_w = semantic_w / total_w
        lexical_w = lexical_w / total_w
        for row in rows:
            sem_raw = float(row.get("semantic_score") or 0.0)
            lex_raw = float(row.get("lexical_score") or 0.0)
            sem_norm = ((sem_raw - sem_min) / (sem_max - sem_min)) if sem_max > sem_min else max(0.0, min(1.0, sem_raw))
            lex_norm = ((lex_raw - lex_min) / (lex_max - lex_min)) if lex_max > lex_min else max(0.0, min(1.0, lex_raw))
            row["semantic_score_norm"] = max(0.0, min(1.0, sem_norm))
            row["lexical_score_norm"] = max(0.0, min(1.0, lex_norm))
            lexical_features = dict(row.get("lexical_features") or {})
            fusion_bonus = (
                (0.06 * float(lexical_features.get("near_exact_score") or 0.0))
                + (0.04 * float(lexical_features.get("exact_phrase_score") or 0.0))
                + (0.03 * float(lexical_features.get("rare_score") or 0.0))
            )
            row["fusion_score"] = max(
                0.0,
                min(
                    1.0,
                    (semantic_w * row["semantic_score_norm"])
                    + (lexical_w * row["lexical_score_norm"])
                    + fusion_bonus,
                ),
            )
            row["fusion_weights"] = {
                "semantic_weight": semantic_w,
                "lexical_weight": lexical_w,
                "fusion_bonus": round(float(fusion_bonus), 4),
            }
        rows.sort(key=lambda x: float(x.get("fusion_score") or 0.0), reverse=True)
        return rows[: max(1, min(limit, 100))]

    async def search_points_with_filters(
        self,
        collection: str,
        query: str | None = None,
        limit: int = 10,
        point_types: list[str] | None = None,
        payload_filter: dict[str, Any] | None = None,
        query_vector: list[float] | None = None,
        lexical_query: str | None = None,
        fusion_semantic_weight: float | None = None,
        fusion_lexical_weight: float | None = None,
        lexical_focus_terms: list[str] | None = None,
        exact_phrases: list[str] | None = None,
        rare_terms: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Keresés expliciten filter-fókuszú API-val (alias)."""
        return await self.search_points(
            collection=collection,
            query=query,
            limit=limit,
            point_types=point_types,
            payload_filter=payload_filter,
            query_vector=query_vector,
            lexical_query=lexical_query,
            fusion_semantic_weight=fusion_semantic_weight,
            fusion_lexical_weight=fusion_lexical_weight,
            lexical_focus_terms=lexical_focus_terms,
            exact_phrases=exact_phrases,
            rare_terms=rare_terms,
        )

    async def search(self, query: str, collection: str, limit: int = 5) -> list[Any]:
        """Vektoros keresés Qdrant-ban."""
        result = await self.search_points(collection=collection, query=query, limit=limit)
        return result

    def delete_collection(self, name: str) -> None:
        """Kollekció törlése Qdrant-ból."""
        self.client.delete_collection(collection_name=name)

    def collection_storage_stats(self, name: str) -> dict[str, int]:
        """Qdrant kollekció becsült vektormérete bájtban."""
        try:
            info = self.client.get_collection(collection_name=name)
        except Exception:
            return {"points_count": 0, "vectors_count": 0, "vector_size": 0, "estimated_bytes": 0}
        points_count = int(getattr(info, "points_count", None) or 0)
        vectors_count = int(getattr(info, "vectors_count", None) or points_count or 0)
        vector_size = int(self.vector_size or 0)
        try:
            vectors_config = getattr(getattr(info, "config", None), "params", None)
            vectors = getattr(vectors_config, "vectors", None)
            if getattr(vectors, "size", None):
                vector_size = int(vectors.size)
        except Exception:
            vector_size = int(self.vector_size or 0)
        estimated_bytes = max(0, vectors_count * vector_size * 4)
        return {
            "points_count": points_count,
            "vectors_count": vectors_count,
            "vector_size": vector_size,
            "estimated_bytes": estimated_bytes,
        }

    async def insert(
        self,
        collection: str,
        title: str,
        content: str,
        vector: list[float],
        point_id: str | None = None,
    ) -> str:
        """Beszúrás Qdrant kollekcióba. Visszaadja a használt point_id-t (loghoz)."""
        pid = self._normalize_point_id(point_id or uuid_lib.uuid4(), point_type="document")

        # Ez a függvény a(z) upsert logikáját valósítja meg.
        def _upsert():
            self.ensure_collection_schema(collection)
            return self.client.upsert(
                collection_name=collection,
                points=[{
                    "id": pid,
                    "vector": vector,
                    "payload": {
                        "title": title,
                        "content": content,
                    }
                }]
            )
        await asyncio.to_thread(_upsert)
        return pid

    def delete_points(self, collection_name: str, point_ids: list[str]) -> None:
        """Point(ok) törlése a kollekcióból (UUID string id-k)."""
        normalized_ids = [self._normalize_point_id(point_id) for point_id in point_ids if str(point_id or "").strip()]
        if not normalized_ids:
            return
        self.client.delete_points(
            collection_name=collection_name,
            points_selector=qm.PointIdsList(points=normalized_ids),
        )

    async def delete_points_by_ids(self, collection_name: str, point_ids: list[str]) -> None:
        """Point(ok) törlése a kollekcióból id-k alapján (async)."""
        if not point_ids:
            return
        await asyncio.to_thread(self.delete_points, collection_name, point_ids)

    async def delete_points_by_source_point_id(self, collection_name: str, source_point_id: str) -> None:
        """Point(ok) törlése source_point_id payload mező alapján."""
        if not source_point_id:
            return
        selector = qm.FilterSelector(
            filter=qm.Filter(
                must=[
                    qm.FieldCondition(
                        key="source_point_id",
                        match=qm.MatchValue(value=source_point_id),
                    )
                ]
            )
        )

        # Ez a függvény törli a(z) delete logikáját.
        def _delete():
            self.client.delete_points(collection_name=collection_name, points_selector=selector)

        await asyncio.to_thread(_delete)
