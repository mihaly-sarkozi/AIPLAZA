"""Lokális entitás-klaszterezés (``LocalResolverV1``) — egy interpretációs futam / forrás kontextusában.

**Ebben a lépésben tilos** (ne implementálj és ne hívj ilyet innen):

- globális profilok létrehozása vagy globális kontextus szerinti egyesítés
- Qdrant index olvasása vagy módosítása
- dokumentumok közötti (*cross-document*) entitás-merge
- nyelvek közötti (*cross-language*) entitás-merge
- LLM vagy más külső generatív / „reasoning” modell hívása
- fuzzy matching vagy közelítő / szándékosan elnéző string-egyeztetés
- similarity / tension engine vagy ezekkel egyenértékű grafikus megkülönböztető réteg
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from apps.knowledge.domain.local_entity_cluster import (
    LocalEntityCluster,
    LocalEntityType,
    local_entity_cluster_to_json_dict,
)
from apps.knowledge.service.entity_key_normalization import normalize_entity_key
from apps.knowledge.service.infer_entity_type_v1 import (
    ENTITY_TYPE_SOURCE_FALLBACK,
    ENTITY_TYPE_SOURCE_KEYWORD,
    ENTITY_TYPE_SOURCE_MENTION_MATCH,
    infer_entity_type,
    infer_entity_type_and_source,
)
from apps.knowledge.service.local_entity_coherence_v1 import coherence_factors_v1, coherence_score_v1
from apps.knowledge.service.local_entity_text_norm import mention_normalized_text, norm_for_overlap


def _try_uuid(value: str | None) -> UUID | None:
    if not value:
        return None
    try:
        return UUID(str(value))
    except ValueError:
        return None


def _coerce_optional_uuid(value: str | UUID | None) -> UUID | None:
    if value is None:
        return None
    if isinstance(value, UUID):
        return value
    return _try_uuid(str(value))


def _mention_index(mentions: list[Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for m in mentions:
        mid = str(getattr(m, "id", "") or "")
        if mid:
            out[mid] = m
    return out


_MIN_SURFACE_NOT_TOO_SHORT = 3
_PLACEHOLDER_SUBJECTS = {
    "it",
    "she",
    "he",
    "they",
    "we",
    "this account",
    "that account",
    "ez",
    "ő",
    "ők",
}


def _is_unresolved_placeholder_subject(subject_text: str | None) -> bool:
    normalized = norm_for_overlap(str(subject_text or ""))
    return normalized in _PLACEHOLDER_SUBJECTS


def _compatible_entity_type_resolution(types_sorted: list[str]) -> tuple[str, str] | None:
    concrete = [t for t in types_sorted if t != LocalEntityType.UNKNOWN.value]
    concrete_set = set(concrete)
    if not concrete or len(concrete_set) <= 1:
        return None
    if concrete_set <= {LocalEntityType.SOFTWARE.value, LocalEntityType.MODULE.value}:
        return LocalEntityType.SOFTWARE.value, "merged_compatible_types"
    if concrete_set <= {
        LocalEntityType.SOFTWARE.value,
        LocalEntityType.MODULE.value,
        LocalEntityType.SYSTEM.value,
    }:
        return LocalEntityType.SOFTWARE.value, "merged_compatible_types"
    return None


def _mention_overlaps_subject(claim: Any, mention: Any) -> bool:
    s_norm = norm_for_overlap(str(getattr(claim, "subject_text", "") or ""))
    if not s_norm:
        return False
    m_norm = norm_for_overlap(mention_normalized_text(mention))
    if not m_norm:
        return False
    if len(m_norm) < 2 and m_norm != s_norm:
        return False
    return m_norm == s_norm or m_norm in s_norm


def _matching_mention_surfaces_for_claim(claim: Any, mention_by_id: dict[str, Any]) -> list[tuple[str, float]]:
    """Ugyanazon mondatban lévő, a subjecthez illeszkedő mentionök felszíne és confidence-e."""
    out: list[tuple[str, float]] = []
    sid = str(getattr(claim, "sentence_id", "") or "")
    for m in mention_by_id.values():
        if str(getattr(m, "sentence_id", "")) != sid:
            continue
        if not _mention_overlaps_subject(claim, m):
            continue
        surf = str(getattr(m, "surface_text", None) or getattr(m, "text_content", "") or "").strip()
        if not surf:
            continue
        conf = float(getattr(m, "confidence", 0.0) or 0.0)
        out.append((surf, conf))
    return out


def _select_canonical_surface(surfaces: list[str], confidence_by_surface: dict[str, float]) -> str:
    """1) leggyakoribb 2) tie: nem túl rövid körből 3) nem csupa kisbetű 4) magasabb confidence 5) rövidebb."""
    stripped = [s.strip() for s in surfaces if s and s.strip()]
    if not stripped:
        return ""
    counts = Counter(stripped)
    max_freq = max(counts.values())
    candidates = sorted({s for s, c in counts.items() if c == max_freq})

    long_enough = [s for s in candidates if len(s) >= _MIN_SURFACE_NOT_TOO_SHORT]
    pool = long_enough if long_enough else list(candidates)

    def sort_key(s: str) -> tuple[int, float, int, str]:
        all_lower = 1 if (s.islower() and any(ch.isalpha() for ch in s)) else 0
        conf = confidence_by_surface.get(s, 0.0)
        return (all_lower, -conf, len(s), s.lower())

    return sorted(pool, key=sort_key)[0]


def _cluster_key(entity_type: str, entity_key: str) -> str:
    label = entity_key or "__empty__"
    return f"{entity_type}\x1f{label}"


def _dedupe_claims_preserve_order(claims: list[Any]) -> list[Any]:
    seen: set[str] = set()
    out: list[Any] = []
    for c in claims:
        cid = str(getattr(c, "claim_id", "") or getattr(c, "id", ""))
        if cid in seen:
            continue
        seen.add(cid)
        out.append(c)
    return out


def _resolve_v1_cluster_groups(
    raw_buckets: dict[tuple[str, str], list[Any]],
) -> tuple[list[tuple[str, str, list[Any]]], list[dict[str, Any]]]:
    """``(normalized_key, entity_type)`` szerinti nyers bucketek → v1 egyesítés / konfliktus szétvágás."""
    by_internal: dict[str, dict[str, list[Any]]] = defaultdict(lambda: defaultdict(list))
    for (norm_key, et), clist in raw_buckets.items():
        internal = norm_key if norm_key else "__empty__"
        by_internal[internal][et].extend(clist)

    for internal in by_internal:
        for et in list(by_internal[internal].keys()):
            by_internal[internal][et] = _dedupe_claims_preserve_order(by_internal[internal][et])

    resolutions: list[dict[str, Any]] = []
    out: list[tuple[str, str, list[Any]]] = []

    for internal in sorted(by_internal.keys()):
        et_map = by_internal[internal]
        types_sorted = sorted(et_map.keys())
        concrete = [t for t in types_sorted if t != LocalEntityType.UNKNOWN.value]
        display_key = "" if internal == "__empty__" else internal

        compatible = _compatible_entity_type_resolution(types_sorted)
        if len(concrete) <= 1 or compatible is not None:
            if compatible is not None:
                resolved_et, res_type = compatible
            else:
                resolved_et = concrete[0] if concrete else LocalEntityType.UNKNOWN.value
                if len(types_sorted) <= 1:
                    res_type = "single"
                elif LocalEntityType.UNKNOWN.value in types_sorted and concrete:
                    res_type = "merged_unknown_into_concrete"
                else:
                    res_type = "merged"
            merged: list[Any] = []
            for et in types_sorted:
                merged.extend(et_map[et])
            merged = _dedupe_claims_preserve_order(merged)
            out.append((display_key, resolved_et, merged))
            resolutions.append(
                {
                    "normalized_key": display_key,
                    "resolution": res_type,
                    "resolved_entity_type": resolved_et,
                    "source_entity_types": types_sorted,
                }
            )
        else:
            resolutions.append(
                {
                    "normalized_key": display_key,
                    "resolution": "conflict_split",
                    "source_entity_types": types_sorted,
                }
            )
            for et in types_sorted:
                cl = et_map[et]
                if cl:
                    out.append((display_key, et, cl))

    out.sort(key=lambda t: (t[0], t[1]))
    return out, resolutions


def _sentence_order_map(sentences: list[Any]) -> dict[str, int]:
    order: dict[str, int] = {}
    for idx, sentence in enumerate(sentences):
        sid = str(getattr(sentence, "id", "") or "")
        if not sid:
            continue
        oi = getattr(sentence, "order_index", idx)
        try:
            oi_int = int(oi)
        except (TypeError, ValueError):
            oi_int = idx
        if sid not in order:
            order[sid] = oi_int
    return order


def _allowed_sentence_ids(sentences: list[Any]) -> set[str] | None:
    if not sentences:
        return None
    out: set[str] = set()
    for sentence in sentences:
        sid = str(getattr(sentence, "id", "") or "")
        if sid:
            out.add(sid)
    return out


def _scoped_mentions(mentions: list[Any], allowed: set[str] | None) -> list[Any]:
    if allowed is None:
        return list(mentions)
    result: list[Any] = []
    for mention in mentions:
        sid = str(getattr(mention, "sentence_id", "") or "")
        if sid in allowed:
            result.append(mention)
    return result


def _scoped_claims(claims: list[Any], allowed: set[str] | None) -> list[Any]:
    if allowed is None:
        return list(claims)
    result: list[Any] = []
    for claim in claims:
        sid = str(getattr(claim, "sentence_id", "") or "")
        if sid in allowed:
            result.append(claim)
    return result


def _claim_sort_key(claim: Any, sentence_order: dict[str, int]) -> tuple[int, str]:
    sid = str(getattr(claim, "sentence_id", "") or "")
    return (sentence_order.get(sid, 10**9), str(getattr(claim, "claim_id", "") or getattr(claim, "id", "")))


def _aggregate_entity_type_source(sources: Iterable[str]) -> str:
    unique = set(sources)
    if ENTITY_TYPE_SOURCE_MENTION_MATCH in unique:
        return ENTITY_TYPE_SOURCE_MENTION_MATCH
    if ENTITY_TYPE_SOURCE_KEYWORD in unique:
        return ENTITY_TYPE_SOURCE_KEYWORD
    return ENTITY_TYPE_SOURCE_FALLBACK


def _claim_evidence_ref(claim: Any) -> dict[str, Any]:
    """Klaszter ``evidence_refs`` egy eleme: a claim subject klaszteréhez kötve."""
    cid = str(getattr(claim, "claim_id", "") or getattr(claim, "id", ""))
    sid_raw = str(getattr(claim, "sentence_id", "") or "")
    pred = str(getattr(claim, "predicate_text", "") or getattr(claim, "predicate", "") or "")
    obj = getattr(claim, "object_text", None)
    obj_s: str | None = None if obj is None else str(obj)
    time_val = getattr(claim, "time_label", None)
    if time_val is None:
        time_val = getattr(claim, "time_value", None)
    space_val = getattr(claim, "space_label", None)
    if space_val is None:
        space_val = getattr(claim, "space_value", None)
    return {
        "sentence_id": sid_raw,
        "claim_id": cid,
        "claim_type": str(getattr(claim, "claim_type", "") or ""),
        "predicate": pred,
        "object_text": obj_s,
        "time_mode": str(getattr(claim, "time_mode", "") or "unknown"),
        "time_value": time_val,
        "space_mode": str(getattr(claim, "space_mode", "") or "unknown"),
        "space_value": space_val,
    }


@dataclass(frozen=True)
class LocalEntityCandidate:
    key: str
    canonical_name: str
    claim_id: str
    sentence_id: str
    entity_type: str
    entity_type_source: str
    confidence_contribution: float

    def as_trace_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "canonical_name": self.canonical_name,
            "claim_id": self.claim_id,
            "sentence_id": self.sentence_id,
            "entity_type": self.entity_type,
            "entity_type_source": self.entity_type_source,
            "confidence_contribution": self.confidence_contribution,
        }


def _build_candidate(claim: Any, mentions: list[Any], *, language: str | None) -> LocalEntityCandidate:
    canonical_name = str(getattr(claim, "subject_text", "") or "").strip()
    key = normalize_entity_key(canonical_name, language)
    entity_type, type_source = infer_entity_type_and_source(claim, mentions)
    conf = float(getattr(claim, "confidence", 0.0) or 0.0)
    return LocalEntityCandidate(
        key=key,
        canonical_name=canonical_name,
        claim_id=str(getattr(claim, "claim_id", "") or getattr(claim, "id", "")),
        sentence_id=str(getattr(claim, "sentence_id", "") or ""),
        entity_type=entity_type,
        entity_type_source=type_source,
        confidence_contribution=conf,
    )


class LocalResolverV1:
    """Lokális entitás-klaszterezés (v1): csak determinisztikus szabályok.

    A modul docstringben felsorolt **tiltások** erre az osztályra és a hívási láncra is érvényesek.

    Csak domain objektumokat és tiszta függvényeket használ — **nincs adatbázis** és **nincs
    repository**; a perzisztencia a hívó réteg (pl. facade + ``LocalEntityClusterRepository``) feladata.

    Minden claim a **subject** (``subject_text`` / normalizált kulcs) klaszterébe kerül;
    az objektum nem külön klaszter-alap v1-ben.

    Csoportosítás: ``(normalized_key, entity_type)``; ugyanazon kulcson több típusnál
    ``unknown`` + egy konkrét típus → egy klaszter a konkrét típussal; egymásnak ellentmondó
    konkrét típusok → külön klaszter. Nincs fuzzy / cross-language egyeztetés v1-ben.
    """

    version: str = "local_resolver_v1"

    def resolve(
        self,
        run_id: str | UUID | None,
        source_id: str | UUID | None,
        sentences: list[Any],
        mentions: list[Any],
        claims: list[Any],
        language: str | None = None,
    ) -> list[LocalEntityCluster]:
        clusters, _trace = self._resolve_impl(
            run_id=run_id,
            source_id=source_id,
            sentences=sentences,
            mentions=mentions,
            claims=claims,
            language=language,
        )
        return clusters

    def resolve_with_trace(
        self,
        run_id: str | UUID | None,
        source_id: str | UUID | None,
        sentences: list[Any],
        mentions: list[Any],
        claims: list[Any],
        language: str | None = None,
    ) -> tuple[list[LocalEntityCluster], dict[str, Any]]:
        """Ugyanaz, mint a ``resolve``, plusz részletes trace (pipeline / meta számára)."""
        return self._resolve_impl(
            run_id=run_id,
            source_id=source_id,
            sentences=sentences,
            mentions=mentions,
            claims=claims,
            language=language,
        )

    def _resolve_impl(
        self,
        *,
        run_id: str | UUID | None,
        source_id: str | UUID | None,
        sentences: list[Any],
        mentions: list[Any],
        claims: list[Any],
        language: str | None,
    ) -> tuple[list[LocalEntityCluster], dict[str, Any]]:
        rid = _coerce_optional_uuid(run_id)
        sid = _coerce_optional_uuid(source_id)

        allowed = _allowed_sentence_ids(sentences)
        sentence_order = _sentence_order_map(sentences)

        mentions_list = _scoped_mentions(mentions, allowed)
        claims_list = _scoped_claims(claims, allowed)

        mention_by_id = _mention_index(mentions_list)

        trace: dict[str, Any] = {
            "resolver_version": self.version,
            "language": language,
            "sentence_count": len(sentences),
            "steps": [],
            "decisions": [],
            "skipped_unresolved_pronoun_entity_count": 0,
        }
        trace["steps"].append({"step": "ingest_claims", "claim_count": len(claims_list)})
        trace["steps"].append({"step": "build_mention_index", "mention_count": len(mentions_list)})
        if allowed is not None:
            trace["steps"].append(
                {
                    "step": "scope_by_sentences",
                    "allowed_sentence_count": len(allowed),
                    "scoped_mention_count": len(mentions_list),
                    "scoped_claim_count": len(claims_list),
                }
            )

        raw_buckets: dict[tuple[str, str], list[Any]] = defaultdict(list)
        for claim in claims_list:
            if _is_unresolved_placeholder_subject(getattr(claim, "subject_text", "")):
                trace["skipped_unresolved_pronoun_entity_count"] = (
                    int(trace.get("skipped_unresolved_pronoun_entity_count") or 0) + 1
                )
                trace["decisions"].append(
                    {
                        "rule": "skip_unresolved_placeholder_subject",
                        "subject_text": str(getattr(claim, "subject_text", "") or ""),
                        "claim_id": str(getattr(claim, "claim_id", "") or getattr(claim, "id", "")),
                    }
                )
                continue
            candidate = _build_candidate(claim, mentions_list, language=language)
            provisional = _cluster_key(candidate.entity_type, candidate.key)
            trace["decisions"].append(
                {
                    "rule": "subject_text_candidate",
                    "provisional_cluster_key": provisional,
                    "candidate": candidate.as_trace_dict(),
                }
            )
            raw_buckets[(candidate.key, candidate.entity_type)].append(claim)

        trace["steps"].append({"step": "raw_buckets", "bucket_count": len(raw_buckets)})

        resolved_groups, entity_resolutions = _resolve_v1_cluster_groups(raw_buckets)
        trace["entity_type_resolutions"] = entity_resolutions
        trace["steps"].append(
            {
                "step": "resolve_entity_type_groups",
                "resolved_cluster_count": len(resolved_groups),
            }
        )

        clusters: list[LocalEntityCluster] = []
        for norm_key, entity_type, bucket_claims in resolved_groups:
            trace_cluster_key = _cluster_key(entity_type, norm_key)
            cluster, materialize_meta = self._materialize_cluster(
                bucket_claims=bucket_claims,
                mention_by_id=mention_by_id,
                mentions_list=mentions_list,
                entity_type=entity_type,
                normalized_key=norm_key,
                run_id=rid,
                source_id=sid,
                sentence_order=sentence_order,
            )
            clusters.append(cluster)
            trace["steps"].append(
                {
                    "step": "materialize_cluster",
                    "cluster_key": trace_cluster_key,
                    **materialize_meta,
                }
            )

        trace["steps"].append({"step": "materialize_clusters", "cluster_count": len(clusters)})
        return clusters, trace

    def _materialize_cluster(
        self,
        *,
        bucket_claims: list[Any],
        mention_by_id: dict[str, Any],
        mentions_list: list[Any],
        entity_type: str,
        normalized_key: str,
        run_id: UUID | None,
        source_id: UUID | None,
        sentence_order: dict[str, int],
    ) -> tuple[LocalEntityCluster, dict[str, Any]]:
        ordered_claims = sorted(bucket_claims, key=lambda c: _claim_sort_key(c, sentence_order))

        mention_ids_set: set[UUID] = set()
        claim_ids: list[UUID] = []
        sentence_ids_set: set[UUID] = set()
        all_surfaces: list[str] = []
        conf_by_surface: dict[str, float] = {}
        evidence_refs: list[dict[str, Any]] = []
        confidences: list[float] = []

        def _bump_conf(surface: str, conf: float) -> None:
            s = surface.strip()
            if not s:
                return
            prev = conf_by_surface.get(s, 0.0)
            if conf > prev:
                conf_by_surface[s] = conf

        for claim in ordered_claims:
            cid = _try_uuid(str(getattr(claim, "claim_id", "") or getattr(claim, "id", "") or ""))
            if cid is not None:
                claim_ids.append(cid)
            sid_raw = str(getattr(claim, "sentence_id", "") or "")
            sid_u = _try_uuid(sid_raw)
            if sid_u is not None:
                sentence_ids_set.add(sid_u)

            mid_raw = getattr(claim, "subject_mention_id", None)
            subject_text = str(getattr(claim, "subject_text", "") or "").strip()
            cconf = float(getattr(claim, "confidence", 0.0) or 0.0)
            if subject_text:
                all_surfaces.append(subject_text)
                _bump_conf(subject_text, cconf)

            for msurf, mconf in _matching_mention_surfaces_for_claim(claim, mention_by_id):
                all_surfaces.append(msurf)
                _bump_conf(msurf, mconf)

            if mid_raw:
                mid = _try_uuid(str(mid_raw))
                if mid is not None:
                    mention_ids_set.add(mid)
            oid_raw = getattr(claim, "object_mention_id", None)
            if oid_raw:
                oid = _try_uuid(str(oid_raw))
                if oid is not None:
                    mention_ids_set.add(oid)

            confidences.append(cconf)
            evidence_refs.append(_claim_evidence_ref(claim))

        canonical = _select_canonical_surface(all_surfaces, conf_by_surface)
        n_claims = len(bucket_claims)
        unique_surfaces = {s.strip() for s in all_surfaces if s.strip()}
        unique_claim_subjects = {
            str(getattr(c, "subject_text", "") or "").strip() for c in ordered_claims
        }
        unique_claim_subjects.discard("")

        confidence = sum(confidences) / len(confidences) if confidences else 0.0
        coherence = coherence_score_v1(
            ordered_claims,
            entity_type=entity_type,
            unique_claim_subject_surfaces=unique_claim_subjects,
            avg_confidence=confidence,
        )
        type_sources = [infer_entity_type_and_source(c, mentions_list)[1] for c in ordered_claims]
        agg_entity_source = _aggregate_entity_type_source(type_sources)
        coherence_factors = coherence_factors_v1(
            ordered_claims,
            entity_type=entity_type,
            unique_claim_subject_surfaces=unique_claim_subjects,
            avg_confidence=confidence,
        )
        explanation: dict[str, Any] = {
            "grouping_rule": "normalized_subject_key",
            "normalized_key": normalized_key,
            "entity_type_source": agg_entity_source,
            "claim_count": n_claims,
            "surface_form_count": len(unique_surfaces),
            "coherence_factors": coherence_factors,
        }

        def _sort_sentence_uuid(u: UUID) -> tuple[int, str]:
            s = str(u)
            return (sentence_order.get(s, 10**9), s)

        cluster = LocalEntityCluster(
            run_id=run_id,
            source_id=source_id,
            canonical_name=canonical,
            entity_type=entity_type,
            normalized_key=normalized_key,
            mention_ids=sorted(mention_ids_set, key=lambda u: str(u)),
            claim_ids=sorted(claim_ids, key=lambda u: str(u)),
            sentence_ids=sorted(sentence_ids_set, key=_sort_sentence_uuid),
            surface_forms=sorted(unique_surfaces),
            evidence_refs=evidence_refs,
            confidence=confidence,
            coherence_score=coherence,
            resolver_version=self.version,
            explanation=explanation,
        )
        meta = {
            "claim_count": n_claims,
            "mention_count": len(mention_ids_set),
            "unique_surface_count": len(unique_surfaces),
            "explanation": explanation,
        }
        return cluster, meta


def attach_local_resolver_metadata(
    metadata: dict[str, Any],
    *,
    clusters: list[LocalEntityCluster],
    trace: dict[str, Any],
) -> dict[str, Any]:
    """Interpretációs / ingest meta mezőbe illeszthető, JSON-kompatibilis kiegészítés."""
    return {
        **metadata,
        "local_resolver_version": trace.get("resolver_version"),
        "local_entity_cluster_count": len(clusters),
        "local_entity_clusters": [local_entity_cluster_to_json_dict(item) for item in clusters],
        "local_resolver_trace": trace,
    }


__all__ = [
    "LocalEntityCandidate",
    "LocalResolverV1",
    "attach_local_resolver_metadata",
    "coherence_factors_v1",
    "coherence_score_v1",
    "infer_entity_type",
    "infer_entity_type_and_source",
    "normalize_entity_key",
]
