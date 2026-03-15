from __future__ import annotations

from time import perf_counter

from apps.knowledge.application.reranker import compute_local_context_score, rerank_items
from config.settings import settings


class KnowledgeContextBuilder:
    """Assertion-first lokális tudáshalmaz építő."""

    def build_context_packet(
        self,
        assertion_hits: list[dict],
        sentence_hits: list[dict],
        chunk_hits: list[dict],
        related_entities: list[dict] | None = None,
        query_focus: dict | None = None,
        top_n: int = 8,
    ) -> dict:
        """Seed + expand + compress logika assertion neighborhood köré szervezve."""
        t_build_start = perf_counter()

        def _estimate_tokens(rows: list[dict]) -> int:
            text = " ".join(str(x.get("text") or x.get("canonical_text") or "") for x in rows)
            words = len([w for w in text.split() if w])
            return max(1, int(words * 1.3))

        def _valid_from(row: dict) -> str:
            return str(row.get("valid_time_from") or row.get("time_from") or "")

        def _valid_to(row: dict) -> str:
            return str(row.get("valid_time_to") or row.get("time_to") or "")

        def _dedupe_rows(rows: list[dict], kind: str) -> list[dict]:
            out: list[dict] = []
            seen_ids: set[str] = set()
            for row in rows:
                rid = str(row.get("id") or row.get(f"{kind}_id") or "")
                if not rid or rid in seen_ids:
                    continue
                seen_ids.add(rid)
                out.append({"kind": kind, **row})
            return out

        def _overlap_ratio(left: list, right: list) -> float:
            left_set = {str(x) for x in left if str(x).strip()}
            right_set = {str(x) for x in right if str(x).strip()}
            if not left_set or not right_set:
                return 0.0
            return len(left_set.intersection(right_set)) / max(1, min(len(left_set), len(right_set)))

        def _interval_overlap_ratio(row: dict, windows: list[tuple[str, str]]) -> float:
            row_from = _valid_from(row)
            row_to = _valid_to(row)
            if not (row_from or row_to):
                return 0.0
            if row.get("time_match"):
                return max(0.0, min(1.0, float(row.get("time_match") or 0.0)))
            for seed_from, seed_to in windows:
                if not (seed_from or seed_to):
                    continue
                if row_from and seed_to and row_from <= seed_to and (not row_to or row_to >= seed_from):
                    return 0.72
                if row_to and seed_from and row_to >= seed_from and (not row_from or row_from <= seed_to):
                    return 0.72
            return 0.0

        def _source_bridge(row: dict, seed_source_points: set[str]) -> float:
            sp = str(row.get("source_point_id") or "").strip()
            return 1.0 if sp and sp in seed_source_points else 0.0

        def _relation_rank(row: dict) -> float:
            return (
                0.55 * float(row.get("relation_confidence") or 0.0)
                + 0.25 * float(row.get("relation_weight") or 0.0)
                + 0.10 * float(row.get("graph_proximity") or 0.0)
                + 0.10 * float(row.get("local_context_score") or 0.0)
            )

        intent = str((query_focus or {}).get("intent") or "summary")
        retrieval_mode = str((query_focus or {}).get("retrieval_mode") or "assertion_first")
        seed_budget = int(getattr(settings, "kb_max_seed_assertions", 8) or 8)
        expanded_budget = int(getattr(settings, "kb_max_expanded_assertions", 12) or 12)
        budget_top_n = max(1, min(top_n, seed_budget + expanded_budget))
        if intent in {"timeline", "status_at_time"}:
            budget_top_n = max(6, budget_top_n)
        elif intent == "comparison":
            budget_top_n = max(8, budget_top_n)

        t_rerank = perf_counter()
        assertion_candidates = rerank_items(_dedupe_rows(assertion_hits, "assertion"))
        direct_seed_candidates = [x for x in assertion_candidates if bool(x.get("is_seed", True))]
        seed_assertions = direct_seed_candidates[:seed_budget] or assertion_candidates[: min(seed_budget, len(assertion_candidates))]
        seed_ids = {str(x.get("id")) for x in seed_assertions}

        seed_entity_ids = {
            int(eid)
            for row in seed_assertions
            for eid in (row.get("entity_ids") or [])
            if isinstance(eid, int)
        }
        seed_place_keys = {
            str(pk).strip()
            for row in seed_assertions
            for pk in ((row.get("place_keys") or []) + (row.get("place_hierarchy_keys") or []))
            if str(pk).strip()
        }
        seed_source_points = {
            str(row.get("source_point_id")).strip()
            for row in seed_assertions
            if str(row.get("source_point_id") or "").strip()
        }
        seed_time_windows = [(_valid_from(row), _valid_to(row)) for row in seed_assertions]

        expanded_candidates: list[dict] = []
        for row in assertion_candidates:
            if str(row.get("id")) in seed_ids:
                continue
            entity_bridge = _overlap_ratio(row.get("entity_ids") or [], list(seed_entity_ids))
            place_bridge = max(
                float(row.get("place_match") or 0.0),
                _overlap_ratio(
                    (row.get("place_keys") or []) + (row.get("place_hierarchy_keys") or []),
                    list(seed_place_keys),
                ),
            )
            time_bridge = _interval_overlap_ratio(row, seed_time_windows)
            evidence_bridge = max(
                _source_bridge(row, seed_source_points),
                0.75 * entity_bridge + 0.25 * time_bridge,
            )
            local_row = dict(row)
            local_row["entity_match"] = max(float(row.get("entity_match") or 0.0), entity_bridge)
            local_row["place_match"] = max(float(row.get("place_match") or 0.0), place_bridge)
            local_row["time_match"] = max(float(row.get("time_match") or 0.0), time_bridge)
            local_row["evidence_bridge_score"] = max(0.0, min(1.0, evidence_bridge))
            local_row["local_context_score"] = compute_local_context_score(local_row)
            expanded_candidates.append(local_row)

        expanded_candidates = sorted(
            expanded_candidates,
            key=lambda x: (
                float(x.get("local_context_score") or 0.0),
                float(x.get("final_score") or 0.0),
                float(x.get("relation_confidence") or 0.0),
            ),
            reverse=True,
        )
        expanded_threshold = float(getattr(settings, "kb_context_min_local_context_score", 0.18) or 0.18)
        expanded_assertions = [
            x for x in expanded_candidates
            if float(x.get("local_context_score") or 0.0) >= expanded_threshold
        ][:expanded_budget]
        if not expanded_assertions:
            expanded_assertions = expanded_candidates[: min(expanded_budget, max(0, budget_top_n - len(seed_assertions)))]

        top_assertions = (seed_assertions + expanded_assertions)[: max(1, budget_top_n)]
        top_assertion_ids = {str(x.get("id")) for x in top_assertions}
        local_assertion_space = {
            "seed_assertion_ids": [x.get("id") for x in seed_assertions],
            "expanded_assertion_ids": [x.get("id") for x in expanded_assertions],
            "seed_source_point_ids": sorted(seed_source_points),
            "seed_entity_ids": sorted(seed_entity_ids),
            "seed_place_keys": sorted(seed_place_keys),
            "assertion_count": len(top_assertions),
        }

        sentence_candidates = rerank_items(_dedupe_rows(sentence_hits, "sentence"))
        chunk_candidates = rerank_items(_dedupe_rows(chunk_hits, "chunk"))
        rerank_ms = (perf_counter() - t_rerank) * 1000.0
        evidence_sentences = [
            x
            for x in sentence_candidates
            if (
                any(str(aid) in top_assertion_ids for aid in (x.get("assertion_ids") or []))
                or str(x.get("source_point_id") or "").strip() in seed_source_points
                or _overlap_ratio(x.get("entity_ids") or [], list(seed_entity_ids)) > 0.0
            )
        ]
        dedup_ev: list[dict] = []
        seen_norm: set[str] = set()
        for row in evidence_sentences:
            norm = " ".join(str(row.get("text") or "").lower().split())
            key = norm[:180]
            if key and key in seen_norm:
                continue
            if key:
                seen_norm.add(key)
            dedup_ev.append(row)
        evidence_sentences = dedup_ev
        source_chunks = [
            x
            for x in chunk_candidates
            if (
                any(str(aid) in top_assertion_ids for aid in (x.get("assertion_ids") or []))
                or str(x.get("source_point_id") or "").strip() in seed_source_points
                or _overlap_ratio(x.get("entity_ids") or [], list(seed_entity_ids)) > 0.0
            )
        ]
        if not top_assertions:
            evidence_sentences = []
            source_chunks = []
        source_chunks = source_chunks[: max(1, int(getattr(settings, "kb_context_max_source_chunks", 3) or 3))]

        time_slice_map: dict[str, dict] = {}
        for row in top_assertions:
            entity_ids = sorted(int(e) for e in (row.get("entity_ids") or []) if isinstance(e, int))
            tf = _valid_from(row)[:10]
            tt = _valid_to(row)[:10]
            places = sorted(str(x) for x in (row.get("place_keys") or []) if str(x).strip())
            key = f"{','.join(str(e) for e in entity_ids)}|{tf}|{tt}|{','.join(places)}"
            bucket = time_slice_map.setdefault(
                key,
                {
                    "slice_key": key,
                    "entity_ids": entity_ids,
                    "valid_time_from": row.get("valid_time_from") or row.get("time_from"),
                    "valid_time_to": row.get("valid_time_to") or row.get("time_to"),
                    "time_from": row.get("valid_time_from") or row.get("time_from"),
                    "time_to": row.get("valid_time_to") or row.get("time_to"),
                    "place_keys": places,
                    "assertion_ids": [],
                    "seed_assertion_ids": [],
                    "expanded_assertion_ids": [],
                    "status_counts": {},
                    "predicate_counts": {},
                    "items": [],
                },
            )
            bucket["assertion_ids"].append(row.get("id"))
            if str(row.get("id")) in seed_ids:
                bucket["seed_assertion_ids"].append(row.get("id"))
            else:
                bucket["expanded_assertion_ids"].append(row.get("id"))
            status = str(row.get("status") or "active").lower()
            bucket["status_counts"][status] = bucket["status_counts"].get(status, 0) + 1
            pred = str(row.get("predicate") or "").strip().lower()
            if pred:
                bucket["predicate_counts"][pred] = bucket["predicate_counts"].get(pred, 0) + 1
            bucket["items"].append(
                {
                    "id": row.get("id"),
                    "text": row.get("text") or row.get("canonical_text"),
                    "seed_role": "seed" if str(row.get("id")) in seed_ids else "expanded",
                    "relation_type": row.get("relation_type"),
                    "relation_weight": row.get("relation_weight"),
                    "relation_confidence": row.get("relation_confidence"),
                    "local_context_score": row.get("local_context_score"),
                }
            )
        time_slice_groups = sorted(
            time_slice_map.values(),
            key=lambda x: (
                len(x.get("seed_assertion_ids") or []),
                len(x.get("assertion_ids") or []),
                str(x.get("valid_time_from") or x.get("valid_time_to") or ""),
            ),
            reverse=True,
        )
        if intent in {"timeline", "status_at_time"}:
            time_slice_groups = sorted(time_slice_groups, key=lambda x: str(x.get("valid_time_from") or x.get("valid_time_to") or ""))

        per_entity_groups: dict[int, dict] = {}
        entity_meta = {
            (int(x.get("entity_id")), str(x.get("kb_uuid") or "")): x
            for x in (related_entities or [])
            if isinstance(x.get("entity_id"), int)
        }
        for row in top_assertions:
            entity_ids = [int(e) for e in (row.get("entity_ids") or []) if isinstance(e, int)]
            for eid in entity_ids:
                bucket = per_entity_groups.setdefault(
                    eid,
                    {
                        "entity_id": eid,
                        "assertion_ids": [],
                        "seed_assertion_ids": [],
                        "expanded_assertion_ids": [],
                        "source_point_ids": [],
                        "activities": {},
                        "relation_types": {},
                        "place_keys": [],
                        "mention_count_in_context": 0,
                    },
                )
                bucket["assertion_ids"].append(row.get("id"))
                if str(row.get("id")) in seed_ids:
                    bucket["seed_assertion_ids"].append(row.get("id"))
                else:
                    bucket["expanded_assertion_ids"].append(row.get("id"))
                sp = str(row.get("source_point_id") or "").strip()
                if sp and sp not in bucket["source_point_ids"]:
                    bucket["source_point_ids"].append(sp)
                for place_key in (row.get("place_keys") or []):
                    if str(place_key).strip() and place_key not in bucket["place_keys"]:
                        bucket["place_keys"].append(place_key)
                pred = str(row.get("predicate") or "").strip().lower()
                if pred:
                    bucket["activities"][pred] = bucket["activities"].get(pred, 0) + 1
                rel = str(row.get("relation_type") or "").strip().upper()
                if rel:
                    bucket["relation_types"][rel] = bucket["relation_types"].get(rel, 0) + 1
                bucket["mention_count_in_context"] += 1

        related_entity_groups = sorted(
            per_entity_groups.values(),
            key=lambda x: (
                len(x.get("seed_assertion_ids") or []),
                len(x.get("assertion_ids") or []),
                x.get("mention_count_in_context") or 0,
            ),
            reverse=True,
        )
        resolved_related_entities: list[dict] = []
        for group in related_entity_groups:
            meta = next((v for (eid, _), v in entity_meta.items() if eid == int(group["entity_id"])), {})
            top_preds = sorted(group.get("activities", {}).items(), key=lambda x: x[1], reverse=True)[:3]
            resolved_related_entities.append(
                {
                    "entity_id": group.get("entity_id"),
                    "kb_uuid": meta.get("kb_uuid"),
                    "canonical_name": meta.get("canonical_name"),
                    "entity_type": meta.get("entity_type"),
                    "aliases": meta.get("aliases") or [],
                    "assertion_ids": group.get("assertion_ids") or [],
                    "seed_assertion_ids": group.get("seed_assertion_ids") or [],
                    "expanded_assertion_ids": group.get("expanded_assertion_ids") or [],
                    "source_point_ids": group.get("source_point_ids") or [],
                    "mention_count_in_context": int(group.get("mention_count_in_context") or 0),
                    "top_predicates": [p for p, _ in top_preds],
                }
            )

        dynamic_groups: dict[str, dict] = {}
        for row in top_assertions:
            entity_ids = sorted(int(e) for e in (row.get("entity_ids") or []) if isinstance(e, int))
            tf = _valid_from(row)[:10]
            tt = _valid_to(row)[:10]
            places = sorted(str(x) for x in (row.get("place_keys") or []) if str(x).strip())
            dkey = f"{','.join(str(e) for e in entity_ids)}|{tf}|{tt}|{','.join(places)}"
            bucket = dynamic_groups.setdefault(
                dkey,
                {
                    "dynamic_chunk_key": dkey,
                    "assertion_ids": [],
                    "seed_assertion_ids": [],
                    "expanded_assertion_ids": [],
                    "entity_ids": entity_ids,
                    "valid_time_from": row.get("valid_time_from") or row.get("time_from"),
                    "valid_time_to": row.get("valid_time_to") or row.get("time_to"),
                    "time_from": row.get("valid_time_from") or row.get("time_from"),
                    "time_to": row.get("valid_time_to") or row.get("time_to"),
                    "source_time": row.get("source_time"),
                    "ingest_time": row.get("ingest_time"),
                    "place_keys": places,
                    "predicate_hints": [],
                    "items": [],
                },
            )
            bucket["assertion_ids"].append(row.get("id"))
            if str(row.get("id")) in seed_ids:
                bucket["seed_assertion_ids"].append(row.get("id"))
            else:
                bucket["expanded_assertion_ids"].append(row.get("id"))
            pred = str(row.get("predicate") or "").strip().lower()
            if pred and pred not in bucket["predicate_hints"]:
                bucket["predicate_hints"].append(pred)
            bucket["items"].append(
                {
                    "assertion_id": row.get("id"),
                    "text": row.get("text") or row.get("canonical_text"),
                    "status": row.get("status"),
                    "relation_type": row.get("relation_type"),
                    "local_context_score": row.get("local_context_score"),
                }
            )
        dynamic_chunks = sorted(
            dynamic_groups.values(),
            key=lambda x: (
                len(x.get("seed_assertion_ids") or []),
                len(x.get("assertion_ids") or []),
            ),
            reverse=True,
        )[: max(3, min(12, budget_top_n))]

        comparison_left = []
        comparison_right = []
        comparison_targets = (query_focus or {}).get("comparison_targets") or []
        if intent == "comparison" and len(comparison_targets) >= 2:
            left_term = str(comparison_targets[0]).lower()
            right_term = str(comparison_targets[1]).lower()
            for row in top_assertions:
                text_low = str(row.get("text") or row.get("canonical_text") or "").lower()
                if left_term and left_term in text_low:
                    comparison_left.append(row)
                elif right_term and right_term in text_low:
                    comparison_right.append(row)

        summary_assertions = seed_assertions[: max(1, min(seed_budget, len(seed_assertions)))]
        key_assertions = (seed_assertions + expanded_assertions)[:seed_budget]
        supporting_assertions = [
            x for x in expanded_assertions
            if str(x.get("relation_type") or "").upper() in {"SUPPORTS", "SAME_SUBJECT", "SAME_OBJECT", "SAME_PREDICATE"}
        ]
        supporting_assertions = sorted(
            supporting_assertions,
            key=lambda x: (_relation_rank(x), float(x.get("final_score") or 0.0)),
            reverse=True,
        )[: int(getattr(settings, "kb_context_max_supporting_assertions", expanded_budget) or expanded_budget)]
        conflicting_assertions = [
            x for x in top_assertions
            if str(x.get("status") or "").lower() == "conflicted"
            or str(x.get("relation_type") or "").upper() == "CONTRADICTS"
        ]
        conflicting_assertions = sorted(
            conflicting_assertions,
            key=lambda x: (_relation_rank(x), float(x.get("confidence") or 0.0)),
            reverse=True,
        )
        superseded_assertions = [
            x for x in top_assertions
            if str(x.get("status") or "").lower() in {"superseded", "partially_superseded", "generalized"}
        ]

        conflict_bundles: list[dict] = []
        if bool(getattr(settings, "kb_context_include_conflicts", True)):
            bundles: dict[str, dict] = {}
            for row in conflicting_assertions:
                key = f"{row.get('predicate')}|{','.join(str(x) for x in (row.get('entity_ids') or []))}"
                bundles.setdefault(
                    key,
                    {
                        "focus_key": key,
                        "items": [],
                        "valid_time_windows": [],
                        "source_point_ids": [],
                        "seed_assertion_ids": [],
                        "expanded_assertion_ids": [],
                    },
                )
                bundles[key]["items"].append(
                    {
                        "assertion_id": row.get("id"),
                        "text": row.get("text") or row.get("canonical_text"),
                        "status": row.get("status"),
                        "confidence": row.get("confidence"),
                        "relation_type": row.get("relation_type"),
                        "relation_weight": row.get("relation_weight"),
                        "relation_confidence": row.get("relation_confidence"),
                        "local_context_score": row.get("local_context_score"),
                    }
                )
                bundles[key]["valid_time_windows"].append(
                    {
                        "from": row.get("valid_time_from") or row.get("time_from"),
                        "to": row.get("valid_time_to") or row.get("time_to"),
                    }
                )
                if str(row.get("id")) in seed_ids:
                    bundles[key]["seed_assertion_ids"].append(row.get("id"))
                else:
                    bundles[key]["expanded_assertion_ids"].append(row.get("id"))
                sp = row.get("source_point_id")
                if sp and sp not in bundles[key]["source_point_ids"]:
                    bundles[key]["source_point_ids"].append(sp)
            conflict_bundles = list(bundles.values())

        refinement_bundles: list[dict] = []
        refine_items = [
            x for x in top_assertions
            if str(x.get("relation_type") or "").upper() in {"REFINES", "GENERALIZES", "TEMPORALLY_SPLITS"}
            or str(x.get("status") or "").lower() in {"refined", "generalized", "partially_superseded"}
        ]
        if refine_items:
            rb: dict[str, dict] = {}
            for row in refine_items:
                key = f"{row.get('predicate')}|{','.join(str(x) for x in (row.get('entity_ids') or []))}"
                rb.setdefault(
                    key,
                    {"focus_key": key, "assertion_ids": [], "seed_assertion_ids": [], "expanded_assertion_ids": [], "items": []},
                )
                rb[key]["assertion_ids"].append(row.get("id"))
                if str(row.get("id")) in seed_ids:
                    rb[key]["seed_assertion_ids"].append(row.get("id"))
                else:
                    rb[key]["expanded_assertion_ids"].append(row.get("id"))
                rb[key]["items"].append(
                    {
                        "id": row.get("id"),
                        "text": row.get("text") or row.get("canonical_text"),
                        "relation_type": row.get("relation_type"),
                        "status": row.get("status"),
                        "relation_weight": row.get("relation_weight"),
                        "relation_confidence": row.get("relation_confidence"),
                        "local_context_score": row.get("local_context_score"),
                    }
                )
            refinement_bundles = sorted(
                list(rb.values()),
                key=lambda b: max(
                    [
                        (0.60 * float(x.get("relation_confidence") or 0.0))
                        + (0.20 * float(x.get("relation_weight") or 0.0))
                        + (0.20 * float(x.get("local_context_score") or 0.0))
                        for x in (b.get("items") or [])
                    ]
                    or [0.0]
                ),
                reverse=True,
            )

        token_budget = int(getattr(settings, "kb_context_token_budget", 2200) or 2200)
        key_budget_rows = key_assertions[: int(getattr(settings, "kb_context_max_key_assertions", seed_budget) or seed_budget)]
        evidence_budget_rows = evidence_sentences[: max(1, int(getattr(settings, "kb_context_max_evidence_per_assertion", 2) or 2) * max(1, len(key_budget_rows)))]
        chunk_budget_rows = source_chunks[: max(1, int(getattr(settings, "kb_context_max_source_chunks", 3) or 3))]
        total_tokens = _estimate_tokens(key_budget_rows) + _estimate_tokens(supporting_assertions) + _estimate_tokens(evidence_budget_rows) + _estimate_tokens(chunk_budget_rows)
        while total_tokens > token_budget and chunk_budget_rows:
            chunk_budget_rows = chunk_budget_rows[:-1]
            total_tokens = _estimate_tokens(key_budget_rows) + _estimate_tokens(supporting_assertions) + _estimate_tokens(evidence_budget_rows) + _estimate_tokens(chunk_budget_rows)
        while total_tokens > token_budget and evidence_budget_rows:
            evidence_budget_rows = evidence_budget_rows[:-1]
            total_tokens = _estimate_tokens(key_budget_rows) + _estimate_tokens(supporting_assertions) + _estimate_tokens(evidence_budget_rows) + _estimate_tokens(chunk_budget_rows)
        while total_tokens > token_budget and len(supporting_assertions) > 1:
            supporting_assertions = supporting_assertions[:-1]
            total_tokens = _estimate_tokens(key_budget_rows) + _estimate_tokens(supporting_assertions) + _estimate_tokens(evidence_budget_rows) + _estimate_tokens(chunk_budget_rows)
        while total_tokens > token_budget and len(key_budget_rows) > 1:
            key_budget_rows = key_budget_rows[:-1]
            total_tokens = _estimate_tokens(key_budget_rows) + _estimate_tokens(supporting_assertions) + _estimate_tokens(evidence_budget_rows) + _estimate_tokens(chunk_budget_rows)
        if total_tokens > token_budget and key_budget_rows:
            for row in key_budget_rows:
                text = str(row.get("text") or row.get("canonical_text") or "")
                if len(text) > 220:
                    row["text"] = text[:220] + "..."
            total_tokens = _estimate_tokens(key_budget_rows) + _estimate_tokens(supporting_assertions) + _estimate_tokens(evidence_budget_rows) + _estimate_tokens(chunk_budget_rows)

        assertion_summaries = []
        for group in related_entity_groups[:4]:
            top_preds = sorted(group.get("activities", {}).items(), key=lambda x: x[1], reverse=True)[:3]
            assertion_summaries.append(
                {
                    "entity_id": group.get("entity_id"),
                    "top_predicates": [p for p, _ in top_preds],
                    "assertion_count": len(group.get("assertion_ids") or []),
                    "seed_assertion_count": len(group.get("seed_assertion_ids") or []),
                    "expanded_assertion_count": len(group.get("expanded_assertion_ids") or []),
                }
            )

        place_context_map: dict[str, dict] = {}
        for row in top_assertions:
            for place_key in (row.get("place_keys") or []):
                key = str(place_key).strip()
                if not key:
                    continue
                bucket = place_context_map.setdefault(
                    key,
                    {
                        "place_key": key,
                        "place_ids": [],
                        "hierarchy_keys": [],
                        "assertion_ids": [],
                        "seed_assertion_ids": [],
                        "expanded_assertion_ids": [],
                        "mention_count_in_context": 0,
                        "best_place_match": 0.0,
                    },
                )
                for place_id in (row.get("place_ids") or []):
                    if isinstance(place_id, int) and place_id > 0 and place_id not in bucket["place_ids"]:
                        bucket["place_ids"].append(place_id)
                for hierarchy_key in (row.get("place_hierarchy_keys") or []):
                    hkey = str(hierarchy_key).strip()
                    if hkey and hkey not in bucket["hierarchy_keys"]:
                        bucket["hierarchy_keys"].append(hkey)
                bucket["assertion_ids"].append(row.get("id"))
                if str(row.get("id")) in seed_ids:
                    bucket["seed_assertion_ids"].append(row.get("id"))
                else:
                    bucket["expanded_assertion_ids"].append(row.get("id"))
                bucket["mention_count_in_context"] += 1
                bucket["best_place_match"] = max(float(bucket.get("best_place_match") or 0.0), float(row.get("place_match") or 0.0))
        related_places = sorted(
            place_context_map.values(),
            key=lambda x: (
                len(x.get("seed_assertion_ids") or []),
                float(x.get("best_place_match") or 0.0),
                int(x.get("mention_count_in_context") or 0),
            ),
            reverse=True,
        )
        per_place_assertion_groups = [
            {
                "place_key": row.get("place_key"),
                "place_ids": row.get("place_ids") or [],
                "hierarchy_keys": row.get("hierarchy_keys") or [],
                "assertion_ids": row.get("assertion_ids") or [],
                "seed_assertion_ids": row.get("seed_assertion_ids") or [],
                "expanded_assertion_ids": row.get("expanded_assertion_ids") or [],
                "mention_count_in_context": row.get("mention_count_in_context") or 0,
                "best_place_match": row.get("best_place_match") or 0.0,
            }
            for row in related_places
        ]

        mention_traces = []
        for row in top_assertions:
            mentions = list(row.get("mentions") or [])
            mention_traces.append(
                {
                    "assertion_id": row.get("id"),
                    "seed_role": "seed" if str(row.get("id")) in seed_ids else "expanded",
                    "sentence_ids": row.get("evidence_sentence_ids") or [],
                    "mention_ids": [m.get("id") for m in mentions if m.get("id") is not None] or (row.get("mention_ids") or []),
                    "entity_ids": row.get("entity_ids") or [],
                    "mentions": mentions,
                }
            )

        valid_from_values = [_valid_from(x) for x in top_assertions if _valid_from(x)]
        valid_to_values = [_valid_to(x) for x in top_assertions if _valid_to(x)]
        source_time_values = [str(x.get("source_time") or "") for x in top_assertions if str(x.get("source_time") or "").strip()]
        ingest_time_values = [str(x.get("ingest_time") or "") for x in top_assertions if str(x.get("ingest_time") or "").strip()]
        relation_rows = [x for x in top_assertions if str(x.get("relation_type") or "").strip()]
        relation_conf_values = [float(x.get("relation_confidence") or 0.0) for x in relation_rows if x.get("relation_confidence") is not None]
        relation_debug_top = [
            {
                "assertion_id": row.get("id"),
                "relation_type": row.get("relation_type"),
                "weight": float(row.get("relation_weight") or 0.0),
                "confidence": float(row.get("relation_confidence") or 0.0),
                "local_context_score": float(row.get("local_context_score") or 0.0),
            }
            for row in sorted(
                relation_rows,
                key=lambda x: (
                    float(x.get("relation_confidence") or 0.0),
                    float(x.get("relation_weight") or 0.0),
                    float(x.get("local_context_score") or 0.0),
                ),
                reverse=True,
            )[:12]
        ]

        return {
            "query_focus": query_focus or {},
            "local_assertion_space": local_assertion_space,
            "seed_assertions": seed_assertions,
            "expanded_assertions": expanded_assertions,
            "top_assertions": top_assertions,
            "key_assertions": key_budget_rows,
            "supporting_assertions": supporting_assertions,
            "conflicting_assertions": conflicting_assertions,
            "superseded_assertions": superseded_assertions if bool(getattr(settings, "kb_context_include_superseded", False)) else [],
            "conflict_bundles": conflict_bundles,
            "refinement_bundles": refinement_bundles,
            "summary_assertions": summary_assertions,
            "evidence_sentences": evidence_budget_rows,
            "source_chunks": chunk_budget_rows,
            "dynamic_chunks": dynamic_chunks,
            "assertion_neighborhoods": dynamic_chunks,
            "assertion_summaries": assertion_summaries,
            "related_entities": resolved_related_entities,
            "related_places": related_places,
            "per_place_assertion_groups": per_place_assertion_groups,
            "time_slice_groups": time_slice_groups,
            "per_entity_assertion_groups": related_entity_groups,
            "primary_entities": resolved_related_entities[:5],
            "assertion_mention_traces": mention_traces,
            "comparison_left": comparison_left,
            "comparison_right": comparison_right,
            "comparison_summary": {
                "enabled": bool(intent == "comparison" and len(comparison_targets) >= 2),
                "left_target": comparison_targets[0] if len(comparison_targets) >= 1 else None,
                "right_target": comparison_targets[1] if len(comparison_targets) >= 2 else None,
                "left_count": len(comparison_left),
                "right_count": len(comparison_right),
            },
            "timeline_sequence": [
                {
                    "assertion_id": row.get("id"),
                    "valid_time_from": row.get("valid_time_from") or row.get("time_from"),
                    "valid_time_to": row.get("valid_time_to") or row.get("time_to"),
                    "time_from": row.get("valid_time_from") or row.get("time_from"),
                    "time_to": row.get("valid_time_to") or row.get("time_to"),
                    "source_time": row.get("source_time"),
                    "ingest_time": row.get("ingest_time"),
                    "seed_role": "seed" if str(row.get("id")) in seed_ids else "expanded",
                    "text": row.get("text") or row.get("canonical_text"),
                }
                for row in sorted(
                    (top_assertions if intent in {"timeline", "status_at_time"} else []),
                    key=lambda x: str(x.get("valid_time_from") or x.get("time_from") or x.get("valid_time_to") or x.get("time_to") or ""),
                )
            ],
            "scoring_summary": {
                "candidates": len(assertion_hits) + len(sentence_hits) + len(chunk_hits),
                "selected": len(top_assertions),
                "seed_count": len(seed_assertions),
                "expanded_count": len(expanded_assertions),
                "retrieval_mode": retrieval_mode,
                "parser_intent": (query_focus or {}).get("intent"),
                "parser_focus_axes": (query_focus or {}).get("focus_axes") or {},
                "parser_audit": (query_focus or {}).get("parser_audit") or {},
                "query_representation": {
                    "raw_query": (query_focus or {}).get("raw_query"),
                    "normalized_query_text": (query_focus or {}).get("normalized_query_text"),
                    "lexical_query_text": (query_focus or {}).get("lexical_query_text"),
                    "query_embedding_text": (query_focus or {}).get("query_embedding_text"),
                },
                "token_budget_top_n": budget_top_n,
                "estimated_tokens": total_tokens,
                "token_budget": token_budget,
                "local_assertion_space": local_assertion_space,
                "time_semantics": {
                    "valid_time": {
                        "from_min": min(valid_from_values) if valid_from_values else None,
                        "to_max": max(valid_to_values) if valid_to_values else None,
                    },
                    "source_time": {
                        "min": min(source_time_values) if source_time_values else None,
                        "max": max(source_time_values) if source_time_values else None,
                    },
                    "ingest_time": {
                        "min": min(ingest_time_values) if ingest_time_values else None,
                        "max": max(ingest_time_values) if ingest_time_values else None,
                    },
                },
                "place_coverage": {
                    "unique_places": len(related_places),
                    "top_places": [x.get("place_key") for x in related_places[:5]],
                    "top_place_matches": [
                        {
                            "place_key": x.get("place_key"),
                            "best_place_match": x.get("best_place_match"),
                            "seed_assertion_count": len(x.get("seed_assertion_ids") or []),
                        }
                        for x in related_places[:5]
                    ],
                },
                "relation_semantics": {
                    "relation_count": len(relation_rows),
                    "confidence_min": min(relation_conf_values) if relation_conf_values else None,
                    "confidence_max": max(relation_conf_values) if relation_conf_values else None,
                    "top_relations": relation_debug_top,
                },
                "mention_trace_count": len([x for x in mention_traces if (x.get("mention_ids") or x.get("mentions"))]),
                "timing_ms": {
                    "rerank": round(rerank_ms, 2),
                    "context_build": round((perf_counter() - t_build_start) * 1000.0, 2),
                },
            },
        }
