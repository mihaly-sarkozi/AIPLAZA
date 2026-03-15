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
        client_kwargs: dict[str, Any] = {
            "url": url,
            "check_compatibility": False,
        }
        if str(api_key or "").strip():
            client_kwargs["api_key"] = api_key
        self.client = QdrantClient(**client_kwargs)
        self.openai = AsyncOpenAI(api_key=openai_key)
        self.embedding_model = embedding_model
        self.vector_size = 3072  # text-embedding-3-large
        self._embedding_cache: dict[str, list[float]] = {}
        self._embedding_cache_order: list[str] = []
        self._embedding_cache_max = 64

    @staticmethod
    def _normalize_lexical_text(text: str) -> str:
        lowered = str(text or "").lower()
        # Egyszerű punctuation cleanup + whitespace normalizálás.
        cleaned = re.sub(r"[^\wáéíóöőúüű\s-]", " ", lowered, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned

    @classmethod
    def _expanded_lexical_tokens(cls, text: str) -> list[str]:
        normalized = cls._normalize_lexical_text(text)
        if not normalized:
            return []
        base_tokens = re.findall(r"[a-z0-9áéíóöőúüű_-]+", normalized)
        expanded: list[str] = []
        seen: set[str] = set()
        for token in base_tokens:
            candidates = [token]
            if "-" in token or "_" in token:
                candidates.extend(part for part in re.split(r"[-_]+", token) if part)
            for candidate in candidates:
                item = str(candidate or "").strip()
                if len(item) < 2 or item in seen:
                    continue
                seen.add(item)
                expanded.append(item)
        return expanded

    @classmethod
    def _lexical_tokens(cls, text: str) -> list[str]:
        # Duplikált tokenek kezelése: query oldalon egyedi készletet használunk.
        return cls._expanded_lexical_tokens(text)

    @staticmethod
    def _token_shape_boost(token: str) -> float:
        if any(ch.isdigit() for ch in token) or "-" in token or "_" in token:
            return 1.0
        if len(token) >= 10:
            return 0.92
        if len(token) >= 8:
            return 0.78
        return 0.45

    @classmethod
    def _payload_lexical_text(cls, payload: dict[str, Any]) -> str:
        parts: list[str] = []
        for key in ("text", "canonical_text", "canonical_name", "predicate"):
            value = str(payload.get(key) or "").strip()
            if value:
                parts.append(value)
        for key in ("aliases", "place_keys", "place_hierarchy_keys"):
            for value in (payload.get(key) or []):
                item = str(value or "").strip()
                if item:
                    parts.append(item)
        return cls._normalize_lexical_text(" ".join(parts))

    @classmethod
    def _near_exact_phrase_score(cls, query_text: str, payload_text: str) -> float:
        q = cls._normalize_lexical_text(query_text)
        p = cls._normalize_lexical_text(payload_text)
        if not q or not p:
            return 0.0
        if q == p:
            return 1.0
        if q in p or p in q:
            shorter = min(len(q), len(p))
            longer = max(len(q), len(p))
            return max(0.0, min(0.96, shorter / max(1, longer)))
        q_compact = q.replace(" ", "")
        p_compact = p.replace(" ", "")
        if q_compact and p_compact and (q_compact in p_compact or p_compact in q_compact):
            shorter = min(len(q_compact), len(p_compact))
            longer = max(len(q_compact), len(p_compact))
            return max(0.0, min(0.92, shorter / max(1, longer)))
        return 0.0

    @classmethod
    def _weighted_overlap_score(cls, query_tokens: list[str], text_tokens: list[str]) -> float:
        if not query_tokens or not text_tokens:
            return 0.0
        text_token_set = set(text_tokens)
        total_weight = 0.0
        matched_weight = 0.0
        for token in query_tokens:
            weight = cls._token_shape_boost(token)
            total_weight += weight
            if token in text_token_set:
                matched_weight += weight
        if total_weight <= 0.0:
            return 0.0
        return max(0.0, min(1.0, matched_weight / total_weight))

    @classmethod
    def _rare_term_score(cls, rare_terms: list[str], payload_text: str, payload_tokens: list[str]) -> float:
        rare_tokens = cls._lexical_tokens(" ".join(rare_terms or []))
        if not rare_tokens:
            return 0.0
        text_norm = cls._normalize_lexical_text(payload_text)
        payload_token_set = set(payload_tokens)
        total = 0.0
        matched = 0.0
        for token in rare_tokens:
            weight = 0.7 + (0.3 * cls._token_shape_boost(token))
            total += weight
            if token in payload_token_set:
                matched += weight
            elif token in text_norm:
                matched += weight * 0.82
        if total <= 0.0:
            return 0.0
        return max(0.0, min(1.0, matched / total))

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
        semantic_w = float(fusion_semantic_weight if fusion_semantic_weight is not None else getattr(settings, "qdrant_fusion_semantic_weight", 0.72))
        lexical_w = float(fusion_lexical_weight if fusion_lexical_weight is not None else getattr(settings, "qdrant_fusion_lexical_weight", 0.28))
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
