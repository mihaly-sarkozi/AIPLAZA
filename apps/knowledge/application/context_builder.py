from __future__ import annotations

from apps.knowledge.application.reranker import rerank_items
from config.settings import settings


class KnowledgeContextBuilder:
    """Assertion + sentence + chunk alapú context csomag építő."""

    def build_context_packet(
        self,
        assertion_hits: list[dict],
        sentence_hits: list[dict],
        chunk_hits: list[dict],
        related_entities: list[dict] | None = None,
        query_focus: dict | None = None,
        top_n: int = 8,
    ) -> dict:
        """Tömör context packet LLM prompthoz."""
        def _estimate_tokens(rows: list[dict]) -> int:
            text = " ".join(str(x.get("text") or x.get("canonical_text") or "") for x in rows)
            words = len([w for w in text.split() if w])
            return max(1, int(words * 1.3))

        intent = str((query_focus or {}).get("intent") or "summary")
        retrieval_mode = str((query_focus or {}).get("retrieval_mode") or "assertion_first")
        merged = []
        seen: set[tuple[str, str]] = set()
        for row in assertion_hits:
            key = ("assertion", str(row.get("id")))
            if key in seen:
                continue
            seen.add(key)
            merged.append({"kind": "assertion", **row})
        for row in sentence_hits:
            key = ("sentence", str(row.get("id")))
            if key in seen:
                continue
            seen.add(key)
            merged.append({"kind": "sentence", **row})
        for row in chunk_hits:
            key = ("chunk", str(row.get("id")))
            if key in seen:
                continue
            seen.add(key)
            merged.append({"kind": "chunk", **row})
        seed_budget = int(getattr(settings, "kb_max_seed_assertions", 8) or 8)
        expanded_budget = int(getattr(settings, "kb_max_expanded_assertions", 12) or 12)
        budget_top_n = max(1, min(top_n, seed_budget + expanded_budget))
        if intent in {"timeline", "status_at_time"}:
            budget_top_n = max(6, budget_top_n)
        elif intent == "comparison":
            budget_top_n = max(8, budget_top_n)
        reranked = rerank_items(merged)[:budget_top_n]
        top_assertions = [x for x in reranked if x.get("kind") == "assertion"]
        seed_assertions = [x for x in top_assertions if bool(x.get("is_seed", True))]
        expanded_assertions = [x for x in top_assertions if not bool(x.get("is_seed", True))]
        top_assertion_ids = {str(x.get("id")) for x in top_assertions}
        evidence_sentences = [
            x for x in reranked if x.get("kind") == "sentence" and (
                not x.get("assertion_ids") or any(str(aid) in top_assertion_ids for aid in (x.get("assertion_ids") or []))
            )
        ]
        # Near-duplicate evidence mondatok összenyomása.
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
            x for x in reranked if x.get("kind") == "chunk" and (
                not x.get("assertion_ids") or any(str(aid) in top_assertion_ids for aid in (x.get("assertion_ids") or []))
            )
        ]
        # Assertion-first guard rail: assertion nélkül ne adjunk vissza sentence/chunk contextet.
        if not top_assertions:
            evidence_sentences = []
            source_chunks = []
        source_chunks = source_chunks[: max(1, int(getattr(settings, "kb_context_max_source_chunks", 3) or 3))]
        # Time-slice aware grouping (entity + időablak).
        grouped: dict[str, dict] = {}
        for row in top_assertions:
            entity_key = ",".join(str(x) for x in sorted([int(e) for e in (row.get("entity_ids") or []) if isinstance(e, int)]))
            tf = str(row.get("time_from") or "")[:10]
            tt = str(row.get("time_to") or "")[:10]
            key = f"{entity_key}|{tf}|{tt}"
            grouped.setdefault(
                key,
                {
                    "entity_ids": row.get("entity_ids") or [],
                    "time_from": row.get("time_from"),
                    "time_to": row.get("time_to"),
                    "assertion_ids": [],
                    "items": [],
                },
            )
            grouped[key]["assertion_ids"].append(row.get("id"))
            grouped[key]["items"].append(
                {
                    "id": row.get("id"),
                    "text": row.get("text") or row.get("canonical_text"),
                    "relation_type": row.get("relation_type"),
                    "relation_weight": row.get("relation_weight"),
                }
            )
        time_slice_groups = list(grouped.values())
        if intent in {"timeline", "status_at_time"}:
            time_slice_groups = sorted(
                time_slice_groups,
                key=lambda x: str(x.get("time_from") or x.get("time_to") or ""),
            )

        # Entity-centric grouping.
        per_entity_groups: dict[int, dict] = {}
        for row in top_assertions:
            entity_ids = [int(e) for e in (row.get("entity_ids") or []) if isinstance(e, int)]
            for eid in entity_ids:
                per_entity_groups.setdefault(
                    eid,
                    {
                        "entity_id": eid,
                        "assertion_ids": [],
                        "activities": {},
                    },
                )
                per_entity_groups[eid]["assertion_ids"].append(row.get("id"))
                pred = str(row.get("predicate") or "").strip().lower()
                if pred:
                    per_entity_groups[eid]["activities"][pred] = per_entity_groups[eid]["activities"].get(pred, 0) + 1

        # DynamicChunk: query-time lokális assertion halmaz (entity/time/place csoport).
        dynamic_groups: dict[str, dict] = {}
        for row in top_assertions:
            entity_ids = sorted(int(e) for e in (row.get("entity_ids") or []) if isinstance(e, int))
            tf = str(row.get("time_from") or "")[:10]
            tt = str(row.get("time_to") or "")[:10]
            places = sorted(str(x) for x in (row.get("place_keys") or []) if str(x).strip())
            dkey = f"{','.join(str(e) for e in entity_ids)}|{tf}|{tt}|{','.join(places)}"
            dynamic_groups.setdefault(
                dkey,
                {
                    "dynamic_chunk_key": dkey,
                    "assertion_ids": [],
                    "entity_ids": entity_ids,
                    "time_from": row.get("time_from"),
                    "time_to": row.get("time_to"),
                    "place_keys": places,
                    "predicate_hints": [],
                    "items": [],
                },
            )
            dynamic_groups[dkey]["assertion_ids"].append(row.get("id"))
            pred = str(row.get("predicate") or "").strip().lower()
            if pred and pred not in dynamic_groups[dkey]["predicate_hints"]:
                dynamic_groups[dkey]["predicate_hints"].append(pred)
            dynamic_groups[dkey]["items"].append(
                {
                    "assertion_id": row.get("id"),
                    "text": row.get("text") or row.get("canonical_text"),
                    "status": row.get("status"),
                    "relation_type": row.get("relation_type"),
                }
            )
        dynamic_chunks = sorted(
            dynamic_groups.values(),
            key=lambda x: len(x.get("assertion_ids") or []),
            reverse=True,
        )[: max(3, min(12, budget_top_n))]

        # Comparison-aware branches.
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

        # Compact summary assertions külön az evidenciától.
        summary_assertions = top_assertions[: max(1, min(seed_budget, len(top_assertions)))]
        key_assertions = [
            x for x in top_assertions
            if str(x.get("status") or "active") in {"active", "refined"}
        ][:seed_budget]
        supporting_assertions = [
            x for x in top_assertions
            if str(x.get("relation_type") or "").upper() in {"SUPPORTS", "SAME_SUBJECT", "SAME_OBJECT", "SAME_PREDICATE"}
        ][: int(getattr(settings, "kb_context_max_supporting_assertions", expanded_budget) or expanded_budget)]
        conflicting_assertions = [
            x for x in top_assertions
            if str(x.get("status") or "").lower() == "conflicted"
            or str(x.get("relation_type") or "").upper() == "CONTRADICTS"
        ]
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
                        "time_windows": [],
                        "source_point_ids": [],
                    },
                )
                bundles[key]["items"].append(
                    {
                        "assertion_id": row.get("id"),
                        "text": row.get("text") or row.get("canonical_text"),
                        "status": row.get("status"),
                        "confidence": row.get("confidence"),
                    }
                )
                bundles[key]["time_windows"].append(
                    {"from": row.get("time_from"), "to": row.get("time_to")}
                )
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
                rb.setdefault(key, {"focus_key": key, "assertion_ids": [], "items": []})
                rb[key]["assertion_ids"].append(row.get("id"))
                rb[key]["items"].append(
                    {
                        "id": row.get("id"),
                        "text": row.get("text") or row.get("canonical_text"),
                        "relation_type": row.get("relation_type"),
                        "status": row.get("status"),
                    }
                )
            refinement_bundles = list(rb.values())

        # Token budget-aware trimming.
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
        if total_tokens > token_budget and len(supporting_assertions) > 1:
            supporting_assertions = supporting_assertions[: max(1, len(supporting_assertions) // 2)]
            total_tokens = _estimate_tokens(key_budget_rows) + _estimate_tokens(supporting_assertions) + _estimate_tokens(evidence_budget_rows) + _estimate_tokens(chunk_budget_rows)
        while total_tokens > token_budget and len(supporting_assertions) > 0:
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
        for group in list(per_entity_groups.values())[:4]:
            top_preds = sorted(group.get("activities", {}).items(), key=lambda x: x[1], reverse=True)[:3]
            assertion_summaries.append(
                {
                    "entity_id": group.get("entity_id"),
                    "top_predicates": [p for p, _ in top_preds],
                    "assertion_count": len(group.get("assertion_ids") or []),
                }
            )

        return {
            "query_focus": query_focus or {},
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
            "assertion_summaries": assertion_summaries,
            "related_entities": related_entities or [],
            "time_slice_groups": time_slice_groups,
            "per_entity_assertion_groups": list(per_entity_groups.values()),
            "primary_entities": [x for x in (related_entities or [])[:5]],
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
                    "time_from": row.get("time_from"),
                    "time_to": row.get("time_to"),
                    "text": row.get("text") or row.get("canonical_text"),
                }
                for row in sorted(
                    (top_assertions if intent in {"timeline", "status_at_time"} else []),
                    key=lambda x: str(x.get("time_from") or x.get("time_to") or ""),
                )
            ],
            "scoring_summary": {
                "candidates": len(merged),
                "selected": len(reranked),
                "seed_count": len(seed_assertions),
                "expanded_count": len(expanded_assertions),
                "retrieval_mode": retrieval_mode,
                "token_budget_top_n": budget_top_n,
                "estimated_tokens": total_tokens,
                "token_budget": token_budget,
            },
        }
