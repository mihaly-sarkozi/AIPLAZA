from qdrant_client import QdrantClient
from qdrant_client import models as qm
from qdrant_client.http.exceptions import UnexpectedResponse
from openai import AsyncOpenAI
from typing import Any
import asyncio
import uuid as uuid_lib
import re
from config.settings import settings


class QdrantUnavailableError(Exception):
    """Qdrant nem elérhető vagy a konfiguráció hibás (pl. 404)."""


class QdrantClientWrapper:
    def __init__(self, url: str, api_key: str, openai_key: str, embedding_model: str = "text-embedding-3-large"):
        self.client = QdrantClient(url=url, api_key=api_key, check_compatibility=False)
        self.openai = AsyncOpenAI(api_key=openai_key)
        self.embedding_model = embedding_model
        self.vector_size = 3072  # text-embedding-3-large
        self._embedding_cache: dict[str, list[float]] = {}
        self._embedding_cache_order: list[str] = []
        self._embedding_cache_max = 64

    async def embed_text(self, text: str) -> list[float]:
        """Szöveg embedding generálása OpenAI API-val."""
        normalized = " ".join(str(text or "").split())
        if normalized in self._embedding_cache:
            return list(self._embedding_cache[normalized])
        response = await self.openai.embeddings.create(
            model=self.embedding_model,
            input=normalized
        )
        vector = response.data[0].embedding
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

        def _exists() -> bool:
            return self.client.collection_exists(collection_name=collection_name)

        try:
            exists = _exists()
        except Exception:
            exists = False

        if exists:
            return
        self.client.create_collection(
            collection_name=collection_name,
            vectors_config=qm.VectorParams(size=target_size, distance=distance),
        )
        # Gyakran szűrt payload mezőkre indexek (best-effort).
        for field_name, schema in [
            ("point_type", qm.PayloadSchemaType.KEYWORD),
            ("kb_uuid", qm.PayloadSchemaType.KEYWORD),
            ("kb_id", qm.PayloadSchemaType.INTEGER),
            ("source_point_id", qm.PayloadSchemaType.KEYWORD),
            ("source_sentence_id", qm.PayloadSchemaType.INTEGER),
            ("subject_entity_id", qm.PayloadSchemaType.INTEGER),
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

    async def ensure_collection_schema_async(
        self,
        collection_name: str,
        vector_size: int | None = None,
    ) -> None:
        await asyncio.to_thread(self.ensure_collection_schema, collection_name, vector_size, qm.Distance.COSINE)

    async def upsert_vector(self, uuid: str, collection: str, vector: list[float], metadata: dict) -> Any:
        """Vektor beszúrása Qdrant kollekcióba (async wrapper sync hívásra)."""
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

    async def _upsert_points(self, collection: str, points: list[dict[str, Any]]) -> Any:
        def _upsert_batch(batch: list[dict[str, Any]]):
            self.ensure_collection_schema(collection)
            return self.client.upsert(collection_name=collection, points=batch)
        result = None
        batch_size = 128
        for i in range(0, len(points), batch_size):
            batch = points[i : i + batch_size]
            result = await asyncio.to_thread(_upsert_batch, batch)
        return result

    async def batch_upsert_points(self, collection: str, points: list[dict[str, Any]]) -> Any:
        """Batch upsert wrapper későbbi bővítésekhez."""
        return await self._upsert_points(collection, points)

    async def _upsert_typed_points(self, collection: str, point_type: str, rows: list[dict[str, Any]]) -> None:
        points: list[dict[str, Any]] = []
        for row in rows:
            text_value = (row.get("text") or row.get("canonical_text") or row.get("canonical_name") or "").strip()
            if not text_value:
                continue
            vector = row.get("vector")
            if vector is None:
                vector = await self.embed_text(text_value)
            point_id = str(row.get("id") or uuid_lib.uuid4())
            payload = dict(row.get("payload") or {})
            payload["point_type"] = point_type
            payload.setdefault("text", text_value)
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

    def _build_filter(self, payload_filter: dict[str, Any] | None = None) -> qm.Filter | None:
        if not payload_filter:
            return None
        must: list[qm.FieldCondition] = []
        for key, value in payload_filter.items():
            if value is None:
                continue
            if isinstance(value, list):
                must.append(
                    qm.FieldCondition(
                        key=key,
                        match=qm.MatchAny(any=value),
                    )
                )
            elif isinstance(value, dict) and any(k in value for k in ["gte", "lte", "gt", "lt"]):
                must.append(
                    qm.FieldCondition(
                        key=key,
                        range=qm.Range(
                            gte=value.get("gte"),
                            lte=value.get("lte"),
                            gt=value.get("gt"),
                            lt=value.get("lt"),
                        ),
                    )
                )
            else:
                must.append(
                    qm.FieldCondition(
                        key=key,
                        match=qm.MatchValue(value=value),
                    )
                )
        if not must:
            return None
        return qm.Filter(must=must)

    async def search_points(
        self,
        collection: str,
        query: str,
        limit: int = 10,
        point_types: list[str] | None = None,
        payload_filter: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Dense similarity keresés payload filterrel + lexical/fusion score előkészítés."""
        vector = await self.embed_text(query)
        effective_filter = dict(payload_filter or {})
        if point_types:
            effective_filter["point_type"] = point_types
        flt = self._build_filter(effective_filter)

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
        q_tokens = {
            t for t in re.findall(r"[a-z0-9áéíóöőúüű_-]+", (query or "").lower())
            if len(t) >= 2
        }
        rows: list[dict[str, Any]] = []
        for hit in raw:
            payload = dict(hit.payload or {})
            text = str(payload.get("text") or "").lower()
            lexical_score = 0.0
            if q_tokens and text:
                text_tokens = {
                    t for t in re.findall(r"[a-z0-9áéíóöőúüű_-]+", text)
                    if len(t) >= 2
                }
                inter = len(q_tokens.intersection(text_tokens))
                token_overlap = inter / max(1, len(q_tokens))
                substring_hits = sum(1 for t in q_tokens if t in text)
                substring_score = substring_hits / max(1, len(q_tokens))
                overlap_w = float(getattr(settings, "qdrant_lexical_overlap_weight", 0.72))
                substring_w = float(getattr(settings, "qdrant_lexical_substring_weight", 0.28))
                lexical_score = (overlap_w * token_overlap) + (substring_w * substring_score)
            semantic = float(hit.score)
            semantic_w = float(getattr(settings, "qdrant_fusion_semantic_weight", 0.72))
            lexical_w = float(getattr(settings, "qdrant_fusion_lexical_weight", 0.28))
            fusion_score = (semantic_w * semantic) + (lexical_w * lexical_score)
            rows.append(
                {
                    "id": str(hit.id),
                    "score": semantic,
                    "semantic_score": semantic,
                    "lexical_score": lexical_score,
                    "fusion_score": fusion_score,
                    "payload": payload,
                }
            )
        rows.sort(key=lambda x: float(x.get("fusion_score") or 0.0), reverse=True)
        return rows[: max(1, min(limit, 100))]

    async def search_points_with_filters(
        self,
        collection: str,
        query: str,
        limit: int = 10,
        point_types: list[str] | None = None,
        payload_filter: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Keresés expliciten filter-fókuszú API-val (alias)."""
        return await self.search_points(
            collection=collection,
            query=query,
            limit=limit,
            point_types=point_types,
            payload_filter=payload_filter,
        )

    async def search(self, query: str, collection: str, limit: int = 5) -> list[Any]:
        """Vektoros keresés Qdrant-ban."""
        result = await self.search_points(collection=collection, query=query, limit=limit)
        return result

    def delete_collection(self, name: str) -> None:
        """Kollekció törlése Qdrant-ból."""
        self.client.delete_collection(collection_name=name)

    async def insert(
        self,
        collection: str,
        title: str,
        content: str,
        vector: list[float],
        point_id: str | None = None,
    ) -> str:
        """Beszúrás Qdrant kollekcióba. Visszaadja a használt point_id-t (loghoz)."""
        pid = point_id or str(uuid_lib.uuid4())

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
        self.client.delete_points(
            collection_name=collection_name,
            points_selector=qm.PointIdsList(points=point_ids),
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

        def _delete():
            self.client.delete_points(collection_name=collection_name, points_selector=selector)

        await asyncio.to_thread(_delete)
