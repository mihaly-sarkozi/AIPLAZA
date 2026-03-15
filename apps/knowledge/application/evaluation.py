from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _load_eval_cases(dataset_path: str) -> list[dict[str, Any]]:
    path = Path(dataset_path)
    raw = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        data = json.loads(raw)
    elif path.suffix.lower() in {".yml", ".yaml"}:
        try:
            import yaml  # type: ignore
        except Exception as e:  # pragma: no cover
            raise RuntimeError("YAML kiértékeléshez szükséges a pyyaml csomag.") from e
        data = yaml.safe_load(raw)
    else:
        data = json.loads(raw)
    if isinstance(data, dict):
        data = data.get("cases") or []
    return [x for x in (data or []) if isinstance(x, dict)]


class RetrievalEvaluationService:
    """Offline retrieval evaluation a meglévő chat context pipeline-ra."""

    def __init__(self, retrieval_service: Any) -> None:
        self.retrieval_service = retrieval_service

    async def run_retrieval_eval(
        self,
        dataset_path: str,
        kb_uuid: str,
        current_user_id: int,
        current_user_role: str | None = None,
        k: int = 8,
        ablation_mode: str = "full_context",
    ) -> dict[str, Any]:
        cases = _load_eval_cases(dataset_path)
        if not cases:
            return {"cases": 0, "metrics": {}}
        total = len(cases)
        entity_hits = 0
        assertion_hits = 0
        evidence_hits = 0
        time_hits = 0
        context_sizes: list[int] = []
        rows: list[dict[str, Any]] = []
        family_stats: dict[str, dict[str, int]] = {}
        fn_rows: list[dict[str, Any]] = []
        fp_rows: list[dict[str, Any]] = []

        for case in cases:
            query = str(case.get("query") or "").strip()
            if not query:
                continue
            parsed_query = {
                "intent": case.get("intent") or "summary",
                "retrieval_mode": case.get("retrieval_mode") or "assertion_first",
            }
            family = str(parsed_query["intent"] or "summary")
            family_stats.setdefault(family, {"total": 0, "entity_hit": 0, "assertion_hit": 0, "evidence_hit": 0, "time_hit": 0})
            family_stats[family]["total"] += 1
            packet = await self.retrieval_service.build_context_for_chat(
                question=query,
                current_user_id=current_user_id,
                current_user_role=current_user_role,
                parsed_query=parsed_query,
                kb_uuid=kb_uuid,
                ablation_mode=ablation_mode,
                debug=True,
            )
            top_assertions = packet.get("top_assertions") or []
            top_ids = {str(x.get("id")) for x in top_assertions[:k]}
            top_entity_ids = {
                int(eid)
                for row in top_assertions[:k]
                for eid in (row.get("entity_ids") or [])
                if isinstance(eid, int)
            }
            expected_entity_ids = {int(x) for x in (case.get("expected_entity_ids") or []) if str(x).isdigit()}
            expected_assertion_ids = {str(x) for x in (case.get("expected_assertion_ids") or [])}
            expected_keywords = [str(x).lower() for x in (case.get("expected_keywords") or []) if str(x).strip()]
            expected_time = case.get("expected_time_window") or {}
            query_time = (packet.get("query_focus") or {}).get("time_window") or {}

            entity_ok = bool(expected_entity_ids.intersection(top_entity_ids)) if expected_entity_ids else True
            assertion_ok = bool(expected_assertion_ids.intersection(top_ids)) if expected_assertion_ids else True
            evidence_text = " ".join(str(x.get("text") or "") for x in (packet.get("evidence_sentences") or []))
            evidence_ok = all(k in evidence_text.lower() for k in expected_keywords) if expected_keywords else True
            time_ok = True
            if expected_time:
                time_ok = (
                    str(expected_time.get("from") or "")[:10] == str(query_time.get("from") or "")[:10]
                    or str(expected_time.get("to") or "")[:10] == str(query_time.get("to") or "")[:10]
                )

            entity_hits += 1 if entity_ok else 0
            assertion_hits += 1 if assertion_ok else 0
            evidence_hits += 1 if evidence_ok else 0
            time_hits += 1 if time_ok else 0
            family_stats[family]["entity_hit"] += 1 if entity_ok else 0
            family_stats[family]["assertion_hit"] += 1 if assertion_ok else 0
            family_stats[family]["evidence_hit"] += 1 if evidence_ok else 0
            family_stats[family]["time_hit"] += 1 if time_ok else 0
            context_sizes.append(
                len(top_assertions)
                + len(packet.get("evidence_sentences") or [])
                + len(packet.get("source_chunks") or [])
            )
            rows.append(
                {
                    "query": query,
                    "intent": family,
                    "entity_hit": entity_ok,
                    "assertion_hit": assertion_ok,
                    "evidence_hit": evidence_ok,
                    "time_hit": time_ok,
                    "context_size": context_sizes[-1],
                }
            )
            if not assertion_ok or not evidence_ok:
                fn_rows.append({"query": query, "intent": family, "reason": "missed_assertion_or_evidence"})
            if assertion_ok and not expected_assertion_ids and len(top_assertions) > max(3, k):
                fp_rows.append({"query": query, "intent": family, "reason": "noisy_assertions"})

        family_report: dict[str, dict[str, float]] = {}
        for fam, stat in family_stats.items():
            total_f = max(1, stat["total"])
            family_report[fam] = {
                "count": float(stat["total"]),
                "entity_recall": round(stat["entity_hit"] / total_f, 4),
                "assertion_recall": round(stat["assertion_hit"] / total_f, 4),
                "evidence_hit_rate": round(stat["evidence_hit"] / total_f, 4),
                "time_correctness": round(stat["time_hit"] / total_f, 4),
            }

        return {
            "cases": total,
            "metrics": {
                "entity_recall": round(entity_hits / max(1, total), 4),
                "assertion_recall_at_k": round(assertion_hits / max(1, total), 4),
                "evidence_sentence_hit_rate": round(evidence_hits / max(1, total), 4),
                "time_correctness": round(time_hits / max(1, total), 4),
                "average_context_size": round(sum(context_sizes) / max(1, len(context_sizes)), 2),
                "ablation_mode": ablation_mode,
            },
            "rows": rows,
            "query_family_report": family_report,
            "audit": {
                "false_negative_candidates": fn_rows[:200],
                "false_positive_candidates": fp_rows[:200],
            },
        }

    @staticmethod
    def suggest_weight_adjustments(eval_output: dict[str, Any]) -> list[dict[str, Any]]:
        metrics = dict((eval_output or {}).get("metrics") or {})
        family = dict((eval_output or {}).get("query_family_report") or {})
        suggestions: list[dict[str, Any]] = []
        if float(metrics.get("time_correctness") or 0.0) < 0.75:
            suggestions.append(
                {
                    "weight": "rerank_time_match_weight",
                    "direction": "increase",
                    "reason": "Időhelyesség alacsony, érdemes növelni a time komponens súlyát.",
                }
            )
        entity_recall = float(metrics.get("entity_recall") or 0.0)
        relation_family = family.get("relation") or {}
        if entity_recall < 0.75 or float(relation_family.get("entity_recall") or 1.0) < 0.75:
            suggestions.append(
                {
                    "weight": "rerank_entity_match_weight",
                    "direction": "increase",
                    "reason": "Entitás-recall alacsony, entity-heavy queryknél erősítés ajánlott.",
                }
            )
        if float(metrics.get("average_context_size") or 0.0) > 28:
            suggestions.append(
                {
                    "weight": "kb_context_token_budget",
                    "direction": "decrease",
                    "reason": "Átlagos context méret nagy, érdemes agresszívebb tömörítést alkalmazni.",
                }
            )
        relation_family = family.get("relation") or {}
        if float(relation_family.get("assertion_recall") or 1.0) < 0.70:
            suggestions.append(
                {
                    "weight": "rerank_relation_confidence_weight",
                    "direction": "increase",
                    "reason": "Kapcsolati kérdéseknél alacsony recall, relation_confidence komponens növelése javasolt.",
                }
            )
        if not suggestions:
            suggestions.append(
                {
                    "weight": "none",
                    "direction": "keep",
                    "reason": "A jelenlegi metrikák alapján nem szükséges súlymódosítás.",
                }
            )
        return suggestions
