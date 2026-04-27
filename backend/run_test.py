from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import types
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4

try:
    import pytest  # noqa: F401
except ModuleNotFoundError:
    class _PytestMarkFallback:
        def __getattr__(self, name: str) -> str:
            return name

    def _xfail(message: str = "") -> None:
        raise RuntimeError(message or "pytest.xfail called outside pytest")

    sys.modules["pytest"] = types.SimpleNamespace(mark=_PytestMarkFallback(), xfail=_xfail)

from tests.integration.knowledge.test_pipeline_regression_v1 import PipelineRegressionHarnessV1
from apps.knowledge.domain.decision_analysis import DecisionAnalysis
from apps.knowledge.domain.search_profile import SearchProfile
from apps.knowledge.service.global_profile_builder_v0 import GlobalProfileBuilderV0


CASE_RE = re.compile(
    r"(?:TEST_CASE:\s*(?P<plain_name>.+?)|===\s*TEST CASE:\s*(?P<banner_name>.+?)\s*===)"
    r"\s+TRAIN:\s*\"\"\"\s*(?P<train>.*?)\s*\"\"\""
    r"\s+QUERY:\s*\"\"\"\s*(?P<query>.*?)\s*\"\"\""
    r"(?:\s+(?:EXPECT|EXPECTED):\s*(?:\"\"\"\s*(?P<expected_block>.*?)\s*\"\"\"|(?P<expected_lines>.*?)(?=\n\s*(?:TEST_CASE:|===\s*TEST CASE:)|\Z)))?",
    re.DOTALL,
)


@dataclass(frozen=True)
class PipelineTestCase:
    name: str
    train: str
    query: str
    expected: dict[str, Any] = field(default_factory=dict)


def _parse_expected(raw: str | None) -> dict[str, Any]:
    text = (raw or "").strip()
    if not text:
        return {}
    expected: dict[str, Any] = {
        "answer_contains": [],
        "answer_not_contains": [],
        "retrieval_chunk_contains": [],
        "feature_check": [],
    }
    parsed_key_value = False
    for line in text.splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        parsed_key_value = True
        if key in {"answer_contains", "answer_not_contains", "retrieval_chunk_contains"}:
            expected.setdefault(key, []).append(value)
        elif key == "feature_check":
            expected.setdefault(key, []).append(value)
        elif key in {"answer_mode"}:
            expected[key] = value
        elif key in {"matched_chunks_min", "matched_claims_min", "global_profiles_min", "global_profiles_max", "global_profiles_exact", "retrieval_chunks_min", "train_claims_min"}:
            expected[key] = int(value)
        elif key in {"evidence_required", "feedback_event_required", "withdrawal_event_required", "index_build", "vector_index_required"}:
            expected[key] = value.lower() in {"1", "true", "yes"}
        elif key in {"feedback_type", "feedback_target_entity", "feedback_claim_text", "feedback_new_claim", "feedback_user_input", "withdraw_source"}:
            expected[key] = value
    if not parsed_key_value:
        expected["answer_contains"].append(" ".join(text.split()))
    if not expected.get("feature_check"):
        expected.pop("feature_check", None)
    return expected


def parse_cases(raw: str) -> list[PipelineTestCase]:
    cases: list[PipelineTestCase] = []
    for match in CASE_RE.finditer(raw):
        cases.append(
            PipelineTestCase(
                name=" ".join((match.group("plain_name") or match.group("banner_name") or "").strip().split()),
                train=match.group("train").strip(),
                query=match.group("query").strip(),
                expected=_parse_expected(match.group("expected_block") or match.group("expected_lines")),
            )
        )
    if not cases:
        raise ValueError("No TEST_CASE/TRAIN/QUERY blocks found")
    return cases


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)


def _summary(trace: dict[str, Any]) -> dict[str, Any]:
    summary = trace.get("summary") if isinstance(trace.get("summary"), dict) else {}
    return {
        "run_id": trace.get("run_id"),
        "source_id": trace.get("source_id"),
        "sentence_count": summary.get("sentence_count"),
        "claim_count": summary.get("claim_count"),
        "global_profile_count": len(trace.get("global_profiles") or []),
        "retrieval_chunk_count": len(trace.get("retrieval_chunks") or []),
    }


def _debug_lines(metadata: dict[str, Any]) -> list[str]:
    query_debug = metadata.get("query_debug") if isinstance(metadata.get("query_debug"), dict) else {}
    return [
        f"matched_chunks_count: {query_debug.get('matched_chunks_count', len(metadata.get('matched_chunks') or []))}",
        f"matched_claims_count: {query_debug.get('matched_claims_count', len(metadata.get('matched_claims') or []))}",
        f"conflict_marker_included: {str(bool(query_debug.get('conflict_marker_included', metadata.get('conflict_marker_included')))).lower()}",
        f"temporal_context_used: {str(bool(query_debug.get('temporal_context_used', metadata.get('temporal_context_used')))).lower()}",
        f"answer_mode: {metadata.get('answer_mode') or 'no_answer'}",
        f"synthesis_confidence: {metadata.get('synthesis_confidence') or 0.0}",
    ]


def _check(condition: bool, label: str, actual: Any | None = None) -> dict[str, Any]:
    item = {"status": "PASS" if condition else "FAIL", "label": label}
    if actual is not None and not condition:
        item["actual"] = actual
    return item


def _trace_claim_count(trace: dict[str, Any]) -> int:
    return sum(len(sentence.get("claims") or []) for sentence in trace.get("sentences") or [])


def _feature_profile(name: str, *, claim_id: str) -> SearchProfile:
    return SearchProfile(
        search_profile_id=uuid4(),
        technical_entity_id=uuid4(),
        entity_name=name,
        entity_type="module",
        normalized_key=name.lower(),
        canonical_key=name.lower(),
        evidence_refs=[{"claim_ids": [claim_id], "sentence_ids": [f"s-{claim_id}"]}],
    )


def _run_feature_check(name: str) -> dict[str, Any]:
    feature = str(name or "").strip().lower()
    if feature == "split":
        existing_candidate = _feature_profile("support service", claim_id="existing-support")
        incoming = _feature_profile("support service", claim_id="incoming-support")
        rows = GlobalProfileBuilderV0().build_many(
            [
                DecisionAnalysis(
                    search_profile_id=incoming.search_profile_id,
                    technical_entity_id=incoming.technical_entity_id,
                    decision="attach_existing",
                    decision_type="attach_existing",
                    selected_candidate_id=str(existing_candidate.technical_entity_id),
                    evidence={"claim_ids": ["incoming-support"], "sentence_ids": ["s-incoming-support"]},
                )
            ],
            [incoming],
            candidate_profiles=[existing_candidate],
            existing_global_profiles=[
                {
                    "profile_id": "global-profile:support-service",
                    "canonical_key": "support service",
                    "entity_name": "support service",
                    "entity_type": "software",
                    "claims": [
                        {"claim_id": "support-claim", "subject": "support service", "predicate": "uses", "object": "Freshdesk", "sentence_ids": ["s-support"]},
                        {"claim_id": "billing-claim", "subject": "billing service", "predicate": "uses", "object": "Stripe", "sentence_ids": ["s-billing"]},
                    ],
                    "evidence": {"claim_ids": ["support-claim", "billing-claim"], "sentence_ids": ["s-support", "s-billing"]},
                }
            ],
        )
        return {
            "feature": "split",
            "passed": len(rows) == 2 and any(row.get("profile_split") is True and row.get("canonical_key") == "billing service" for row in rows),
            "actual": rows,
        }
    if feature == "merge":
        first = _feature_profile("support service", claim_id="support-c-1")
        second = _feature_profile("support service", claim_id="support-c-2")
        rows = GlobalProfileBuilderV0().build_many(
            [
                DecisionAnalysis(
                    search_profile_id=first.search_profile_id,
                    technical_entity_id=first.technical_entity_id,
                    decision="create_new_profile",
                    decision_type="create_new_profile",
                    evidence={"claim_ids": ["support-c-1"], "sentence_ids": ["s-support-c-1"]},
                ),
                DecisionAnalysis(
                    search_profile_id=second.search_profile_id,
                    technical_entity_id=second.technical_entity_id,
                    decision="create_new_profile",
                    decision_type="create_new_profile",
                    evidence={"claim_ids": ["support-c-2"], "sentence_ids": ["s-support-c-2"]},
                ),
            ],
            [first, second],
        )
        return {
            "feature": "merge",
            "passed": len(rows) == 1 and rows[0].get("profile_merged") is True and rows[0].get("claim_deduplicated_count") == 1,
            "actual": rows,
        }
    return {"feature": feature, "passed": False, "actual": f"unknown feature_check: {name}"}


def evaluate_case(case: PipelineTestCase, result: dict[str, Any], retrieval_chunk: str) -> dict[str, Any]:
    expected = case.expected
    metadata: dict[str, Any] = result["metadata"]
    train_trace: dict[str, Any] = result["train_trace"]
    actions: dict[str, Any] = result.get("actions") or {}
    answer_text = str(metadata.get("answer_text") or "")
    answer_mode = str(metadata.get("answer_mode") or "no_answer")
    query_debug = metadata.get("query_debug") if isinstance(metadata.get("query_debug"), dict) else {}
    checks: list[dict[str, Any]] = []
    for value in expected.get("answer_contains") or []:
        checks.append(_check(value in answer_text, f'answer contains "{value}"', answer_text))
    for value in expected.get("answer_not_contains") or []:
        checks.append(_check(value not in answer_text, f'answer does not contain "{value}"', answer_text))
    if expected.get("answer_mode"):
        checks.append(_check(answer_mode == expected["answer_mode"], f"answer_mode is {expected['answer_mode']}", answer_mode))
    if "matched_chunks_min" in expected:
        actual = int(query_debug.get("matched_chunks_count", len(metadata.get("matched_chunks") or [])))
        checks.append(_check(actual >= int(expected["matched_chunks_min"]), f"matched_chunks_count >= {expected['matched_chunks_min']}", actual))
    if "matched_claims_min" in expected:
        actual = int(query_debug.get("matched_claims_count", len(metadata.get("matched_claims") or [])))
        checks.append(_check(actual >= int(expected["matched_claims_min"]), f"matched_claims_count >= {expected['matched_claims_min']}", actual))
    for value in expected.get("retrieval_chunk_contains") or []:
        checks.append(_check(value in retrieval_chunk, f'retrieval chunk contains "{value}"', retrieval_chunk))
    if "global_profiles_min" in expected:
        actual = len(train_trace.get("global_profiles") or [])
        checks.append(_check(actual >= int(expected["global_profiles_min"]), f"global_profile_count >= {expected['global_profiles_min']}", actual))
    if "global_profiles_max" in expected:
        actual = len(train_trace.get("global_profiles") or [])
        checks.append(_check(actual <= int(expected["global_profiles_max"]), f"global_profile_count <= {expected['global_profiles_max']}", actual))
    if "global_profiles_exact" in expected:
        actual = len(train_trace.get("global_profiles") or [])
        checks.append(_check(actual == int(expected["global_profiles_exact"]), f"global_profile_count == {expected['global_profiles_exact']}", actual))
    if "retrieval_chunks_min" in expected:
        actual = len(train_trace.get("retrieval_chunks") or [])
        checks.append(_check(actual >= int(expected["retrieval_chunks_min"]), f"retrieval_chunk_count >= {expected['retrieval_chunks_min']}", actual))
    if "train_claims_min" in expected:
        actual = _trace_claim_count(train_trace)
        checks.append(_check(actual >= int(expected["train_claims_min"]), f"train claim_count >= {expected['train_claims_min']}", actual))
    if expected.get("feedback_event_required"):
        checks.append(_check(bool(actions.get("feedback")), "feedback action returned event", actions.get("feedback")))
        checks.append(_check(bool(metadata.get("feedback_events")), "query metadata feedback_events not empty", metadata.get("feedback_events")))
    if expected.get("withdrawal_event_required"):
        checks.append(_check(bool(actions.get("withdrawal")), "withdrawal action returned event", actions.get("withdrawal")))
        checks.append(_check(bool(metadata.get("source_withdrawal_events")), "query metadata source_withdrawal_events not empty", metadata.get("source_withdrawal_events")))
    if expected.get("vector_index_required"):
        index_build = actions.get("index_build") or {}
        checks.append(_check(bool(index_build.get("retrieval_chunk_indexed")), "retrieval chunks indexed for vector search", index_build))
        checks.append(_check(bool(getattr(result.get("query_run"), "build_ids", []) or []), "query used ready index build", getattr(result.get("query_run"), "build_ids", [])))
    for feature_name in expected.get("feature_check") or []:
        feature_result = _run_feature_check(feature_name)
        checks.append(_check(bool(feature_result.get("passed")), f"{feature_name} feature check passes", feature_result.get("actual")))
    if expected.get("evidence_required"):
        checks.append(_check(bool(metadata.get("cited_claim_ids")), "cited_claim_ids not empty", metadata.get("cited_claim_ids")))
        checks.append(_check(bool(metadata.get("cited_sentence_ids")), "cited_sentence_ids not empty", metadata.get("cited_sentence_ids")))
        checks.append(_check(bool(metadata.get("cited_source_ids") or metadata.get("source_ids")), "cited_source_ids not empty", metadata.get("cited_source_ids") or metadata.get("source_ids")))
        explanation = metadata.get("explanation") if isinstance(metadata.get("explanation"), dict) else {}
        checks.append(_check(bool(explanation.get("claims")), "explanation claims not empty", explanation))
        checks.append(_check(bool(explanation.get("sentences")), "explanation sentences not empty", explanation))
        checks.append(_check(bool(explanation.get("sources")), "explanation sources not empty", explanation))
    passed = all(item["status"] == "PASS" for item in checks)
    return {"passed": passed, "checks": checks}


def _render_checks(checks: list[dict[str, Any]]) -> str:
    if not checks:
        return "[PASS] no explicit checks"
    lines = []
    for check in checks:
        line = f"[{check['status']}] {check['label']}"
        if check.get("actual") is not None:
            line += f"\n  actual: {_json(check['actual']) if isinstance(check['actual'], (dict, list)) else check['actual']}"
        lines.append(line)
    return "\n".join(lines)


def _render_evidence_display(explanation: dict[str, Any]) -> str:
    claims = explanation.get("claims") if isinstance(explanation.get("claims"), list) else []
    sentences = explanation.get("sentences") if isinstance(explanation.get("sentences"), list) else []
    sources = explanation.get("sources") if isinstance(explanation.get("sources"), list) else []
    lines: list[str] = []
    for claim in claims:
        if isinstance(claim, dict) and claim.get("claim_text"):
            lines.append(f"- Claim: {claim['claim_text']}")
    for sentence in sentences:
        if isinstance(sentence, dict):
            sentence_text = str(sentence.get("sentence_text") or sentence.get("sentence_id") or "").strip()
            if sentence_text:
                lines.append(f'- Sentence: "{sentence_text}"')
    for source in sources:
        if isinstance(source, dict) and source.get("source_id"):
            lines.append(f"- Source: {source['source_id']}")
    return "\n".join(lines) if lines else "(no explanation evidence)"


async def _query(harness: PipelineRegressionHarnessV1, query: str):
    return await harness.facade.retrieve(
        tenant="demo",
        corpus_uuid="kb-regression",
        query=query,
    )


async def _run_index_build(harness: PipelineRegressionHarnessV1) -> dict[str, Any]:
    build = harness.facade.schedule_index_build(
        tenant="demo",
        corpus_uuid="kb-regression",
        index_profile_key="basic_chunk_v1",
        created_by=None,
    )
    completed = await harness.facade.run_index_build(build.id)
    return {
        "build_id": completed.id,
        "status": completed.status,
        "collection_name": completed.collection_name,
        **dict(completed.metadata or {}),
    }


def run_case(case: PipelineTestCase) -> dict[str, Any]:
    harness = PipelineRegressionHarnessV1()
    train_trace = harness.run_text(case.train)
    actions: dict[str, Any] = {}
    expected = case.expected
    if expected.get("feedback_type"):
        actions["feedback"] = harness.facade.apply_knowledge_feedback(
            tenant="demo",
            corpus_uuid="kb-regression",
            target_entity=str(expected.get("feedback_target_entity") or ""),
            claim_text=str(expected.get("feedback_claim_text") or ""),
            feedback_type=str(expected.get("feedback_type") or ""),
            optional_new_claim=str(expected.get("feedback_new_claim") or "").strip() or None,
            user_input=str(expected.get("feedback_user_input") or "").strip() or None,
        )
    if expected.get("withdraw_source"):
        requested_source = str(expected.get("withdraw_source") or "").strip()
        source_id = str(train_trace.get("source_id") or "").strip() if requested_source == "first_source" else requested_source
        actions["withdrawal"] = harness.facade.withdraw_source(
            tenant="demo",
            corpus_uuid="kb-regression",
            source_id=source_id,
            user_input=f"withdraw_source({source_id})",
        )
    if expected.get("index_build") or expected.get("vector_index_required"):
        actions["index_build"] = asyncio.run(_run_index_build(harness))
    query_run = asyncio.run(_query(harness, case.query))
    metadata = dict(query_run.metadata or {})
    return {
        "case": case,
        "train_trace": train_trace,
        "query_run": query_run,
        "metadata": metadata,
        "actions": actions,
    }


def render_case(result: dict[str, Any]) -> str:
    case: PipelineTestCase = result["case"]
    metadata: dict[str, Any] = result["metadata"]
    matched_chunks = metadata.get("matched_chunks") or []
    retrieval_chunk = ""
    if matched_chunks:
        retrieval_chunk = str((matched_chunks[0] or {}).get("retrieval_chunk_text") or "")
    elif result["train_trace"].get("retrieval_chunks"):
        retrieval_chunk = str((result["train_trace"]["retrieval_chunks"][0] or {}).get("retrieval_chunk_text") or "")
    evaluation = evaluate_case(case, result, retrieval_chunk)
    evidence = metadata.get("evidence_summary") or (metadata.get("query_debug") or {}).get("evidence") or []
    explanation = metadata.get("explanation") if isinstance(metadata.get("explanation"), dict) else {}

    parts = [
        f"=== TEST CASE: {case.name} ===",
        "",
        "--- TRAIN ---",
        case.train,
        "",
        "--- QUERY ---",
        case.query,
        "",
        "--- EXPECT ---",
        _json(case.expected),
        "",
        f"RESULT: {'PASS' if evaluation['passed'] else 'FAIL'}",
        "Checks:",
        _render_checks(evaluation["checks"]),
        "",
        "--- TRAIN RESPONSE SUMMARY ---",
        _json(_summary(result["train_trace"])),
        "",
        "--- ACTIONS ---",
        _json(result.get("actions") or {}),
        "",
        "--- ANSWER ---",
        str(metadata.get("answer_text") or ""),
        "",
        "--- DEBUG ---",
        "\n".join(_debug_lines(metadata)),
        "",
        "--- QUERY PROFILE ---",
        _json(metadata.get("query_profile") or {}),
        "",
        "--- MATCHED CHUNKS ---",
        _json(matched_chunks),
        "",
        "--- MATCHED CLAIMS ---",
        _json(metadata.get("matched_claims") or []),
        "",
        "--- EVIDENCE ---",
        _json(evidence),
        "",
        "--- EXPLANATION ---",
        _json(explanation),
        "",
        "--- EVIDENCE DISPLAY ---",
        _render_evidence_display(explanation),
        "",
        "--- RETRIEVAL CHUNK ---",
        retrieval_chunk,
        "",
    ]
    return "\n".join(parts).rstrip()


def default_output_path(input_path: Path) -> Path:
    return Path("test_results") / input_path.name


def main() -> int:
    parser = argparse.ArgumentParser(description="Run knowledge pipeline test cases from a text script.")
    parser.add_argument("script", type=Path, help="Path to a TEST_CASE script, e.g. tests/london_test.txt")
    parser.add_argument("--output", type=Path, default=None, help="Output log path. Defaults to test_results/<input-name>.")
    args = parser.parse_args()

    raw = args.script.read_text(encoding="utf-8")
    cases = parse_cases(raw)
    rendered: list[str] = []
    passed = 0
    for case in cases:
        result = run_case(case)
        rendered_case = render_case(result)
        rendered.append(rendered_case)
        if "RESULT: PASS" in rendered_case:
            passed += 1
    summary = "\n".join(
        [
            "=== SUMMARY ===",
            f"Total: {len(cases)}",
            f"Passed: {passed}",
            f"Failed: {len(cases) - passed}",
        ]
    )

    output_path = args.output or default_output_path(args.script)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n\n".join([*rendered, summary]) + "\n", encoding="utf-8")
    print(f"Wrote {len(cases)} test case result(s) to {output_path}")
    print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
